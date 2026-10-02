"""SQL de ganadería: especies, categorías, animales (o grupos de animales) y sus eventos."""
from datetime import date, timedelta

from app.nucleo.database import Archivado, NoEncontrado, TieneHistorial, conectar, filas_a_dicts
from app.nucleo.utilidades import normalizar_texto


class AnimalNoEncontrado(NoEncontrado):
    """Se pidió un animal que no existe."""


class EventoInvalido(Exception):
    """El evento o el dato no tiene sentido para ese animal (ej: parto de un toro)."""


# Eventos que solo puede tener una hembra (no un grupo) de una especie con gestación.
EVENTOS_REPRODUCTIVOS = ("parto", "aborto", "tacto", "servicio")

CAMPOS_ANIMAL = (
    "caravana", "categoria_id", "es_grupo", "cantidad", "raza", "rodeo", "fecha_nacimiento",
    "estado_reproductivo", "fecha_probable_parto", "madre_id", "estado", "observaciones",
)

# "reproductiva" = puede preñarse: hembra, individual y de una especie con días de gestación.
SELECT_ANIMALES = """
    SELECT a.*, c.nombre AS categoria, c.sexo, c.especie_id,
           e.nombre AS especie, e.dias_gestacion,
           (c.sexo = 'hembra' AND a.es_grupo = 0 AND e.dias_gestacion IS NOT NULL) AS reproductiva,
           madre.caravana AS madre_caravana,
           (SELECT COUNT(*) FROM eventos_animales ev WHERE ev.animal_id = a.id AND ev.tipo = 'parto') AS partos,
           (SELECT MAX(fecha) FROM eventos_animales ev WHERE ev.animal_id = a.id) AS ultimo_evento
    FROM animales a
    JOIN categorias_animal c ON c.id = a.categoria_id
    JOIN especies e ON e.id = c.especie_id
    LEFT JOIN animales madre ON madre.id = a.madre_id
"""


# ---------- Especies y categorías ----------

def listar_especies():
    """Especies con sus categorías y cuántos animales activos hay de cada una."""
    with conectar() as conexion:
        especies = filas_a_dicts(conexion.execute(
            "SELECT * FROM especies ORDER BY nombre COLLATE NOCASE"
        ).fetchall())
        categorias = filas_a_dicts(conexion.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM animales a WHERE a.categoria_id = c.id) AS animales,
                   (SELECT COALESCE(SUM(a.cantidad), 0) FROM animales a
                     WHERE a.categoria_id = c.id AND a.estado = 'activo') AS cabezas
            FROM categorias_animal c ORDER BY c.id
            """
        ).fetchall())
    for especie in especies:
        especie["categorias"] = [c for c in categorias if c["especie_id"] == especie["id"]]
        especie["animales"] = sum(c["animales"] for c in especie["categorias"])
        especie["cabezas"] = sum(c["cabezas"] for c in especie["categorias"])
    return especies


def obtener_especie(especie_id):
    return next((e for e in listar_especies() if e["id"] == especie_id), None)


def agregar_especie(nombre, dias_gestacion=None):
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO especies (nombre, dias_gestacion) VALUES (?, ?)", (nombre, dias_gestacion)
        )
        nuevo_id = cursor.lastrowid
    return obtener_especie(nuevo_id)


def editar_especie(especie_id, nombre, dias_gestacion=None):
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE especies SET nombre = ?, dias_gestacion = ? WHERE id = ?", (nombre, dias_gestacion, especie_id)
        )
        if cursor.rowcount == 0:
            raise NoEncontrado()
        # Sin días de gestación, sus animales ya no pueden estar preñados.
        if dias_gestacion is None:
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = '', fecha_probable_parto = NULL "
                "WHERE categoria_id IN (SELECT id FROM categorias_animal WHERE especie_id = ?)",
                (especie_id,),
            )
    return obtener_especie(especie_id)


def eliminar_especie(especie_id):
    """Borra una especie SOLO si no tiene animales (sus categorías se borran con ella)."""
    with conectar() as conexion:
        if conexion.execute("SELECT 1 FROM especies WHERE id = ?", (especie_id,)).fetchone() is None:
            raise NoEncontrado()
        tiene_animales = conexion.execute(
            "SELECT 1 FROM animales a JOIN categorias_animal c ON c.id = a.categoria_id "
            "WHERE c.especie_id = ? LIMIT 1", (especie_id,)
        ).fetchone()
        if tiene_animales:
            raise TieneHistorial()
        conexion.execute("DELETE FROM categorias_animal WHERE especie_id = ?", (especie_id,))
        conexion.execute("DELETE FROM especies WHERE id = ?", (especie_id,))


def obtener_categoria(categoria_id):
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT c.*, e.nombre AS especie, e.dias_gestacion FROM categorias_animal c "
            "JOIN especies e ON e.id = c.especie_id WHERE c.id = ?", (categoria_id,)
        ).fetchone()
        return dict(fila) if fila else None


def agregar_categoria(especie_id, nombre, sexo=""):
    with conectar() as conexion:
        if conexion.execute("SELECT 1 FROM especies WHERE id = ?", (especie_id,)).fetchone() is None:
            raise NoEncontrado()
        cursor = conexion.execute(
            "INSERT INTO categorias_animal (especie_id, nombre, sexo) VALUES (?, ?, ?)", (especie_id, nombre, sexo)
        )
        nuevo_id = cursor.lastrowid
    return obtener_categoria(nuevo_id)


def editar_categoria(categoria_id, nombre, sexo=""):
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE categorias_animal SET nombre = ?, sexo = ? WHERE id = ?", (nombre, sexo, categoria_id)
        )
        if cursor.rowcount == 0:
            raise NoEncontrado()
        # Si deja de ser hembra, sus animales ya no pueden estar preñados.
        if sexo != "hembra":
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = '', fecha_probable_parto = NULL WHERE categoria_id = ?",
                (categoria_id,),
            )
    return obtener_categoria(categoria_id)


def eliminar_categoria(categoria_id):
    """Borra una categoría SOLO si ningún animal la usa."""
    with conectar() as conexion:
        if conexion.execute("SELECT 1 FROM animales WHERE categoria_id = ? LIMIT 1", (categoria_id,)).fetchone():
            raise TieneHistorial()
        cursor = conexion.execute("DELETE FROM categorias_animal WHERE id = ?", (categoria_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


# ---------- Animales ----------

def _obtener_animal(conexion, animal_id):
    fila = conexion.execute(SELECT_ANIMALES + " WHERE a.id = ?", (animal_id,)).fetchone()
    return dict(fila) if fila else None


def obtener_animal(animal_id):
    with conectar() as conexion:
        return _obtener_animal(conexion, animal_id)


def listar_animales(incluir_bajas=False):
    condicion = "" if incluir_bajas else " WHERE a.estado = 'activo'"
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            SELECT_ANIMALES + condicion + " ORDER BY a.caravana COLLATE NOCASE, e.nombre COLLATE NOCASE"
        ).fetchall())


def _categoria(conexion, categoria_id):
    fila = conexion.execute(
        "SELECT c.*, e.dias_gestacion FROM categorias_animal c JOIN especies e ON e.id = c.especie_id WHERE c.id = ?",
        (categoria_id,),
    ).fetchone()
    if fila is None:
        raise EventoInvalido("Esa categoría no existe. Elegí una de la lista (o creala en Especies).")
    return dict(fila)


def _limpiar(conexion, datos: dict) -> dict:
    """Ordena los datos según la categoría y si es un grupo.

    - Un animal individual siempre cuenta como 1. Un grupo no tiene madre.
    - Solo una hembra individual de una especie con gestación tiene estado reproductivo.
    """
    datos = dict(datos)
    categoria = _categoria(conexion, datos["categoria_id"])
    datos["es_grupo"] = 1 if datos.get("es_grupo") else 0
    if datos["es_grupo"]:
        datos["madre_id"] = None
    else:
        datos["cantidad"] = 1
    reproductiva = categoria["sexo"] == "hembra" and not datos["es_grupo"] and categoria["dias_gestacion"]
    if not reproductiva:
        datos["estado_reproductivo"] = ""
        datos["fecha_probable_parto"] = None
    elif datos.get("estado_reproductivo") != "prenada":
        datos["fecha_probable_parto"] = None
    for campo in ("fecha_nacimiento", "fecha_probable_parto"):
        if datos.get(campo) is not None:
            datos[campo] = str(datos[campo])
    _verificar_madre(conexion, datos.get("madre_id"), categoria["especie_id"], datos.get("id"))
    return datos


def _verificar_madre(conexion, madre_id, especie_id, animal_id=None):
    if madre_id is None:
        return
    if madre_id == animal_id:
        raise EventoInvalido("Un animal no puede ser su propia madre.")
    madre = _obtener_animal(conexion, madre_id)
    if madre is None:
        raise AnimalNoEncontrado()
    if madre["sexo"] != "hembra" or madre["es_grupo"]:
        raise EventoInvalido(f"La madre ({madre['caravana']}) tiene que ser una hembra (no un grupo).")
    if madre["especie_id"] != especie_id:
        raise EventoInvalido(f"La madre ({madre['caravana']}) es de otra especie ({madre['especie']}).")


def agregar_animal(datos: dict):
    with conectar() as conexion:
        datos = _limpiar(conexion, datos)
        cursor = conexion.execute(
            f"INSERT INTO animales ({', '.join(CAMPOS_ANIMAL)}) VALUES ({', '.join('?' for _ in CAMPOS_ANIMAL)})",
            [datos.get(c) for c in CAMPOS_ANIMAL],
        )
        return _obtener_animal(conexion, cursor.lastrowid)


def editar_animal(animal_id, datos: dict):
    with conectar() as conexion:
        if _obtener_animal(conexion, animal_id) is None:
            raise AnimalNoEncontrado()
        datos = _limpiar(conexion, {**datos, "id": animal_id})
        conexion.execute(
            f"UPDATE animales SET {', '.join(f'{c} = ?' for c in CAMPOS_ANIMAL)} WHERE id = ?",
            [datos.get(c) for c in CAMPOS_ANIMAL] + [animal_id],
        )
        return _obtener_animal(conexion, animal_id)


def eliminar_animal(animal_id):
    """Borra un animal SOLO si no tiene eventos ni crías. Si no, se da de baja."""
    with conectar() as conexion:
        if _obtener_animal(conexion, animal_id) is None:
            raise AnimalNoEncontrado()
        tiene_eventos = conexion.execute(
            "SELECT 1 FROM eventos_animales WHERE animal_id = ? LIMIT 1", (animal_id,)
        ).fetchone()
        tiene_crias = conexion.execute(
            "SELECT 1 FROM animales WHERE madre_id = ? LIMIT 1", (animal_id,)
        ).fetchone()
        if tiene_eventos or tiene_crias:
            raise TieneHistorial()
        conexion.execute("DELETE FROM animales WHERE id = ?", (animal_id,))


def listar_crias(animal_id):
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            SELECT_ANIMALES + " WHERE a.madre_id = ? ORDER BY a.fecha_nacimiento DESC", (animal_id,)
        ).fetchall())


def partos_proximos(hasta):
    """Hembras activas preñadas con fecha probable de parto <= hasta (incluye atrasadas)."""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            SELECT_ANIMALES + " WHERE a.estado = 'activo' AND a.estado_reproductivo = 'prenada' "
            "AND a.fecha_probable_parto IS NOT NULL AND a.fecha_probable_parto <= ? "
            "ORDER BY a.fecha_probable_parto",
            (str(hasta),),
        ).fetchall())


# ---------- Eventos ----------

def listar_eventos(animal_id):
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            "SELECT * FROM eventos_animales WHERE animal_id = ? ORDER BY fecha DESC, id DESC",
            (animal_id,),
        ).fetchall())


def _fecha_parto_desde_servicio(conexion, animal):
    """Si hay un servicio registrado, la fecha probable de parto es servicio + días de gestación."""
    fila = conexion.execute(
        "SELECT MAX(fecha) FROM eventos_animales WHERE animal_id = ? AND tipo = 'servicio'",
        (animal["id"],),
    ).fetchone()
    if fila[0] is None:
        return None
    return date.fromisoformat(fila[0]) + timedelta(days=animal["dias_gestacion"])


def _motivo_no_reproductiva(animal, tipo):
    """Explica por qué ese animal no puede tener un parto, tacto, etc."""
    if animal["es_grupo"]:
        return f"{animal['caravana']} es un grupo: un {tipo} se carga animal por animal."
    if animal["sexo"] != "hembra":
        return f"{animal['caravana']} es {animal['categoria'].lower()}: no puede tener un {tipo}."
    return (f"La especie {animal['especie']} no tiene días de gestación cargados: "
            f"agregalos en Especies para registrar un {tipo}.")


def _categoria_al_parir(conexion, animal):
    """Una vaquillona (vacuno) que pare pasa a ser vaca. En otras especies no cambia."""
    if normalizar_texto(animal["especie"]) != "vacuno" or normalizar_texto(animal["categoria"]) != "vaquillona":
        return animal["categoria_id"]
    vaca = conexion.execute(
        "SELECT id FROM categorias_animal WHERE especie_id = ? AND nombre = 'Vaca' COLLATE NOCASE",
        (animal["especie_id"],),
    ).fetchone()
    return vaca[0] if vaca else animal["categoria_id"]


def registrar_evento(animal_id, fecha, tipo, resultado="", crias_machos=0, crias_hembras=0,
                     detalle="", fecha_probable_parto=None):
    """Guarda un evento y actualiza el estado del animal, TODO en la misma transacción.

    - parto:  la hembra queda "vacía" (una vaquillona pasa a ser vaca).
    - aborto: la hembra queda "vacía".
    - tacto:  resultado "prenada" o "vacia". Si está preñada, calcula la fecha probable
              de parto (la que se pasa, o último servicio + días de gestación de la especie).
    - servicio, sanidad, observación: solo quedan registrados.
    Devuelve el animal actualizado.
    """
    with conectar() as conexion:
        animal = _obtener_animal(conexion, animal_id)
        if animal is None:
            raise AnimalNoEncontrado()
        if animal["estado"] != "activo":
            raise Archivado()

        if tipo in EVENTOS_REPRODUCTIVOS and not animal["reproductiva"]:
            raise EventoInvalido(_motivo_no_reproductiva(animal, tipo))
        if tipo == "parto" and crias_machos + crias_hembras == 0:
            raise EventoInvalido("Indicá cuántas crías (machos y/o hembras). Si nació muerta, anotalo en el detalle.")
        if tipo == "tacto" and resultado not in ("prenada", "vacia"):
            raise EventoInvalido("En un tacto, el resultado tiene que ser 'preñada' o 'vacía'.")
        if tipo != "tacto":
            resultado = ""
        if tipo != "parto":
            crias_machos = crias_hembras = 0

        conexion.execute(
            "INSERT INTO eventos_animales (animal_id, fecha, tipo, resultado, crias_machos, crias_hembras, detalle) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (animal_id, str(fecha), tipo, resultado, crias_machos, crias_hembras, detalle),
        )

        if tipo in ("parto", "aborto") or (tipo == "tacto" and resultado == "vacia"):
            nueva_categoria = _categoria_al_parir(conexion, animal) if tipo == "parto" else animal["categoria_id"]
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = 'vacia', fecha_probable_parto = NULL, "
                "categoria_id = ? WHERE id = ?",
                (nueva_categoria, animal_id),
            )
        elif tipo == "tacto" and resultado == "prenada":
            fpp = fecha_probable_parto or _fecha_parto_desde_servicio(conexion, animal)
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = 'prenada', fecha_probable_parto = ? WHERE id = ?",
                (str(fpp) if fpp else None, animal_id),
            )

        return _obtener_animal(conexion, animal_id)


def listar_nacimientos():
    """Todos los partos y abortos, con los datos de la madre (para el resumen de crías).

    "crias_con_caravana": cuántas crías de esa madre se cargaron como animales,
    nacidas hasta 30 días alrededor del parto (las crías no guardan de qué parto son).
    """
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            """
            SELECT ev.id, ev.fecha, ev.tipo, ev.crias_machos, ev.crias_hembras, ev.detalle,
                   a.id AS madre_id, a.caravana AS madre_caravana, a.rodeo, a.estado AS madre_estado,
                   c.nombre AS madre_categoria, e.id AS especie_id, e.nombre AS especie,
                   (SELECT COUNT(*) FROM animales cria
                     WHERE cria.madre_id = a.id AND cria.fecha_nacimiento IS NOT NULL
                       AND abs(julianday(cria.fecha_nacimiento) - julianday(ev.fecha)) <= 30
                   ) AS crias_con_caravana
            FROM eventos_animales ev
            JOIN animales a ON a.id = ev.animal_id
            JOIN categorias_animal c ON c.id = a.categoria_id
            JOIN especies e ON e.id = c.especie_id
            WHERE ev.tipo IN ('parto', 'aborto')
            ORDER BY ev.fecha DESC, ev.id DESC
            """
        ).fetchall())


def eliminar_evento(evento_id):
    """Borra un evento cargado por error. OJO: no deshace el cambio de estado del animal."""
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM eventos_animales WHERE id = ?", (evento_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()
