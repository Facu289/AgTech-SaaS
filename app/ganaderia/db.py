"""SQL de ganadería: animales (uno por caravana) y sus eventos."""
from datetime import date, timedelta

from app.nucleo.database import Archivado, NoEncontrado, TieneHistorial, conectar, filas_a_dicts
from app.nucleo.opciones import DIAS_GESTACION, HEMBRAS


class AnimalNoEncontrado(NoEncontrado):
    """Se pidió un animal que no existe."""


class EventoInvalido(Exception):
    """El evento no tiene sentido para ese animal (ej: parto de un toro)."""


CAMPOS_ANIMAL = (
    "caravana", "categoria", "raza", "rodeo", "fecha_nacimiento",
    "estado_reproductivo", "fecha_probable_parto", "madre_id", "estado", "observaciones",
)

SELECT_ANIMALES = """
    SELECT a.*, madre.caravana AS madre_caravana,
           (SELECT COUNT(*) FROM eventos_animales e WHERE e.animal_id = a.id AND e.tipo = 'parto') AS partos,
           (SELECT MAX(fecha) FROM eventos_animales e WHERE e.animal_id = a.id) AS ultimo_evento
    FROM animales a
    LEFT JOIN animales madre ON madre.id = a.madre_id
"""


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
            SELECT_ANIMALES + condicion + " ORDER BY a.caravana COLLATE NOCASE"
        ).fetchall())


def _limpiar(datos: dict) -> dict:
    """Los machos no tienen estado reproductivo ni fecha de parto."""
    datos = dict(datos)
    if datos.get("categoria") not in HEMBRAS:
        datos["estado_reproductivo"] = ""
        datos["fecha_probable_parto"] = None
    elif datos.get("estado_reproductivo") != "prenada":
        datos["fecha_probable_parto"] = None
    for campo in ("fecha_nacimiento", "fecha_probable_parto"):
        if datos.get(campo) is not None:
            datos[campo] = str(datos[campo])
    return datos


def _verificar_madre(conexion, madre_id, animal_id=None):
    if madre_id is None:
        return
    if madre_id == animal_id:
        raise EventoInvalido("Un animal no puede ser su propia madre.")
    madre = _obtener_animal(conexion, madre_id)
    if madre is None:
        raise AnimalNoEncontrado()
    if madre["categoria"] not in HEMBRAS:
        raise EventoInvalido(f"La madre ({madre['caravana']}) tiene que ser una hembra.")


def agregar_animal(datos: dict):
    datos = _limpiar(datos)
    with conectar() as conexion:
        _verificar_madre(conexion, datos.get("madre_id"))
        cursor = conexion.execute(
            f"INSERT INTO animales ({', '.join(CAMPOS_ANIMAL)}) VALUES ({', '.join('?' for _ in CAMPOS_ANIMAL)})",
            [datos.get(c) for c in CAMPOS_ANIMAL],
        )
        return _obtener_animal(conexion, cursor.lastrowid)


def editar_animal(animal_id, datos: dict):
    datos = _limpiar(datos)
    with conectar() as conexion:
        _verificar_madre(conexion, datos.get("madre_id"), animal_id)
        cursor = conexion.execute(
            f"UPDATE animales SET {', '.join(f'{c} = ?' for c in CAMPOS_ANIMAL)} WHERE id = ?",
            [datos.get(c) for c in CAMPOS_ANIMAL] + [animal_id],
        )
        if cursor.rowcount == 0:
            raise AnimalNoEncontrado()
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


def _fecha_parto_desde_servicio(conexion, animal_id):
    """Si hay un servicio registrado, la fecha probable de parto es servicio + 283 días."""
    fila = conexion.execute(
        "SELECT MAX(fecha) FROM eventos_animales WHERE animal_id = ? AND tipo = 'servicio'",
        (animal_id,),
    ).fetchone()
    if fila[0] is None:
        return None
    return date.fromisoformat(fila[0]) + timedelta(days=DIAS_GESTACION)


def registrar_evento(animal_id, fecha, tipo, resultado="", crias_machos=0, crias_hembras=0,
                     detalle="", fecha_probable_parto=None):
    """Guarda un evento y actualiza el estado del animal, TODO en la misma transacción.

    - parto:  la hembra queda "vacía" (una vaquillona pasa a ser vaca).
    - aborto: la hembra queda "vacía".
    - tacto:  resultado "prenada" o "vacia". Si está preñada, calcula la fecha
              probable de parto (la que se pasa, o último servicio + 283 días).
    - servicio, sanidad, observación: solo quedan registrados.
    Devuelve el animal actualizado.
    """
    with conectar() as conexion:
        animal = _obtener_animal(conexion, animal_id)
        if animal is None:
            raise AnimalNoEncontrado()
        if animal["estado"] != "activo":
            raise Archivado()

        reproductivo = tipo in ("parto", "aborto", "tacto", "servicio")
        if reproductivo and animal["categoria"] not in HEMBRAS:
            raise EventoInvalido(f"{animal['caravana']} es {animal['categoria']}: no puede tener un {tipo}.")
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
            nueva_categoria = "vaca" if (tipo == "parto" and animal["categoria"] == "vaquillona") else animal["categoria"]
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = 'vacia', fecha_probable_parto = NULL, "
                "categoria = ? WHERE id = ?",
                (nueva_categoria, animal_id),
            )
        elif tipo == "tacto" and resultado == "prenada":
            fpp = fecha_probable_parto or _fecha_parto_desde_servicio(conexion, animal_id)
            conexion.execute(
                "UPDATE animales SET estado_reproductivo = 'prenada', fecha_probable_parto = ? WHERE id = ?",
                (str(fpp) if fpp else None, animal_id),
            )

        return _obtener_animal(conexion, animal_id)


def eliminar_evento(evento_id):
    """Borra un evento cargado por error. OJO: no deshace el cambio de estado del animal."""
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM eventos_animales WHERE id = ?", (evento_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()
