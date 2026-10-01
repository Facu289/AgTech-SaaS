"""SQL de maquinaria: máquinas, mantenimientos, trabajos, vencimientos y contactos."""
from app.nucleo.database import NoEncontrado, TieneHistorial, conectar, filas_a_dicts
from app.nucleo.opciones import AVISO_SERVICE_PORCENTAJE


class MaquinaNoEncontrada(NoEncontrado):
    """Se pidió una máquina que no existe."""


CAMPOS_MAQUINA = (
    "nombre", "tipo", "marca", "modelo", "anio", "numero_serie", "serie_monitor", "patente",
    "horas_motor", "horas_trilla", "observaciones",
)

SELECT_MAQUINAS = """
    SELECT m.*,
           (SELECT MAX(fecha) FROM mantenimientos WHERE maquina_id = m.id AND tipo = 'service') AS ultimo_service,
           (SELECT horas FROM mantenimientos WHERE maquina_id = m.id AND tipo = 'service'
             ORDER BY fecha DESC, id DESC LIMIT 1) AS horas_ultimo_service,
           (SELECT COALESCE(SUM(hectareas), 0) FROM trabajos WHERE maquina_id = m.id) AS hectareas_totales,
           (SELECT MIN(fecha_vencimiento) FROM vencimientos
             WHERE maquina_id = m.id AND resuelto = 0) AS proximo_vencimiento
    FROM maquinas m
"""


# ---------- Máquinas ----------

def _obtener_maquina(conexion, maquina_id):
    fila = conexion.execute(SELECT_MAQUINAS + " WHERE m.id = ?", (maquina_id,)).fetchone()
    return dict(fila) if fila else None


def obtener_maquina(maquina_id):
    with conectar() as conexion:
        return _obtener_maquina(conexion, maquina_id)


def listar_maquinas(incluir_archivadas=False):
    condicion = "" if incluir_archivadas else " WHERE m.archivado = 0"
    with conectar() as conexion:
        return filas_a_dicts(
            conexion.execute(SELECT_MAQUINAS + condicion + " ORDER BY m.tipo, m.nombre").fetchall()
        )


def agregar_maquina(datos: dict):
    columnas = ", ".join(CAMPOS_MAQUINA)
    signos = ", ".join("?" for _ in CAMPOS_MAQUINA)
    with conectar() as conexion:
        cursor = conexion.execute(
            f"INSERT INTO maquinas ({columnas}) VALUES ({signos})",
            [datos.get(campo) for campo in CAMPOS_MAQUINA],
        )
        return _obtener_maquina(conexion, cursor.lastrowid)


def editar_maquina(maquina_id, datos: dict):
    asignaciones = ", ".join(f"{campo} = ?" for campo in CAMPOS_MAQUINA)
    with conectar() as conexion:
        cursor = conexion.execute(
            f"UPDATE maquinas SET {asignaciones} WHERE id = ?",
            [datos.get(campo) for campo in CAMPOS_MAQUINA] + [maquina_id],
        )
        if cursor.rowcount == 0:
            raise MaquinaNoEncontrada()
        return _obtener_maquina(conexion, maquina_id)


def actualizar_horas(maquina_id, horas_motor=None, horas_trilla=None):
    """Actualiza el horómetro (solo los valores que se pasan)."""
    with conectar() as conexion:
        if _obtener_maquina(conexion, maquina_id) is None:
            raise MaquinaNoEncontrada()
        if horas_motor is not None:
            conexion.execute("UPDATE maquinas SET horas_motor = ? WHERE id = ?", (horas_motor, maquina_id))
        if horas_trilla is not None:
            conexion.execute("UPDATE maquinas SET horas_trilla = ? WHERE id = ?", (horas_trilla, maquina_id))
        return _obtener_maquina(conexion, maquina_id)


def archivar_maquina(maquina_id, archivado=True):
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE maquinas SET archivado = ? WHERE id = ?", (int(archivado), maquina_id)
        )
        if cursor.rowcount == 0:
            raise MaquinaNoEncontrada()
        return _obtener_maquina(conexion, maquina_id)


def eliminar_maquina(maquina_id):
    """Borra una máquina SOLO si no tiene nada asociado. Si no, hay que archivarla."""
    with conectar() as conexion:
        if _obtener_maquina(conexion, maquina_id) is None:
            raise MaquinaNoEncontrada()
        for tabla in ("mantenimientos", "trabajos", "vencimientos", "insumo_maquinas", "planes_service"):
            usado = conexion.execute(
                f"SELECT 1 FROM {tabla} WHERE maquina_id = ? LIMIT 1", (maquina_id,)
            ).fetchone()
            if usado:
                raise TieneHistorial()
        conexion.execute("DELETE FROM maquinas WHERE id = ?", (maquina_id,))


# ---------- Mantenimientos (services y arreglos) ----------

def listar_mantenimientos(maquina_id):
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            "SELECT * FROM mantenimientos WHERE maquina_id = ? ORDER BY fecha DESC, id DESC",
            (maquina_id,),
        ).fetchall())


def agregar_mantenimiento(maquina_id, fecha, tipo, descripcion, horas=None, costo=None, plan_ids=()):
    """Guarda un service/arreglo. Si las horas son mayores al horómetro, lo actualiza.

    plan_ids: planes de service programado que este service deja "hechos"
    (su contador vuelve a empezar desde las horas actuales).
    """
    with conectar() as conexion:
        maquina = _obtener_maquina(conexion, maquina_id)
        if maquina is None:
            raise MaquinaNoEncontrada()
        cursor = conexion.execute(
            "INSERT INTO mantenimientos (maquina_id, fecha, tipo, horas, descripcion, costo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (maquina_id, str(fecha), tipo, horas, descripcion, costo),
        )
        if horas is not None and horas > maquina["horas_motor"]:
            conexion.execute("UPDATE maquinas SET horas_motor = ? WHERE id = ?", (horas, maquina_id))
        # El contador de los planes vuelve a empezar desde las horas de ESTE service.
        horas_motor = horas if horas is not None else maquina["horas_motor"]
        _marcar_planes_hechos(conexion, maquina_id, plan_ids, fecha, horas_motor, maquina["horas_trilla"] or 0)
        fila = conexion.execute("SELECT * FROM mantenimientos WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(fila)


def eliminar_mantenimiento(mantenimiento_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM mantenimientos WHERE id = ?", (mantenimiento_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


# ---------- Trabajos (hectáreas) ----------

def listar_trabajos(maquina_id=None, desde=None, hasta=None, tipo=None):
    condiciones, valores = [], []
    if maquina_id is not None:
        condiciones.append("t.maquina_id = ?")
        valores.append(maquina_id)
    if tipo:
        condiciones.append("t.tipo = ?")
        valores.append(tipo)
    if desde:
        condiciones.append("t.fecha >= ?")
        valores.append(str(desde))
    if hasta:
        condiciones.append("t.fecha <= ?")
        valores.append(str(hasta))
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            "SELECT t.*, m.nombre AS maquina_nombre FROM trabajos t "
            "JOIN maquinas m ON m.id = t.maquina_id" + donde + " ORDER BY t.fecha DESC, t.id DESC",
            valores,
        ).fetchall())


def agregar_trabajo(maquina_id, fecha, tipo, hectareas, lote="", cultivo="", observaciones=""):
    with conectar() as conexion:
        if _obtener_maquina(conexion, maquina_id) is None:
            raise MaquinaNoEncontrada()
        cursor = conexion.execute(
            "INSERT INTO trabajos (maquina_id, fecha, tipo, hectareas, lote, cultivo, observaciones) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (maquina_id, str(fecha), tipo, hectareas, lote, cultivo, observaciones),
        )
        fila = conexion.execute("SELECT * FROM trabajos WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(fila)


def eliminar_trabajo(trabajo_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM trabajos WHERE id = ?", (trabajo_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


# ---------- Vencimientos ----------

SELECT_VENCIMIENTOS = """
    SELECT v.*, m.nombre AS maquina_nombre, m.serie_monitor AS maquina_serie_monitor
    FROM vencimientos v LEFT JOIN maquinas m ON m.id = v.maquina_id
"""


def listar_vencimientos(incluir_resueltos=False, maquina_id=None):
    condiciones, valores = [], []
    if not incluir_resueltos:
        condiciones.append("v.resuelto = 0")
    if maquina_id is not None:
        condiciones.append("v.maquina_id = ?")
        valores.append(maquina_id)
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            SELECT_VENCIMIENTOS + donde + " ORDER BY v.resuelto, v.fecha_vencimiento", valores
        ).fetchall())


def vencimientos_proximos(hasta):
    """Vencimientos sin resolver con fecha <= hasta (incluye los ya vencidos)."""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            SELECT_VENCIMIENTOS + " WHERE v.resuelto = 0 AND v.fecha_vencimiento <= ? "
            "ORDER BY v.fecha_vencimiento",
            (str(hasta),),
        ).fetchall())


def _obtener_vencimiento(conexion, vencimiento_id):
    fila = conexion.execute(SELECT_VENCIMIENTOS + " WHERE v.id = ?", (vencimiento_id,)).fetchone()
    return dict(fila) if fila else None


def agregar_vencimiento(descripcion, tipo, fecha_vencimiento, maquina_id=None, observaciones=""):
    with conectar() as conexion:
        if maquina_id is not None and _obtener_maquina(conexion, maquina_id) is None:
            raise MaquinaNoEncontrada()
        cursor = conexion.execute(
            "INSERT INTO vencimientos (descripcion, tipo, fecha_vencimiento, maquina_id, observaciones) "
            "VALUES (?, ?, ?, ?, ?)",
            (descripcion, tipo, str(fecha_vencimiento), maquina_id, observaciones),
        )
        return _obtener_vencimiento(conexion, cursor.lastrowid)


def editar_vencimiento(vencimiento_id, descripcion, tipo, fecha_vencimiento, maquina_id, observaciones, resuelto):
    with conectar() as conexion:
        if maquina_id is not None and _obtener_maquina(conexion, maquina_id) is None:
            raise MaquinaNoEncontrada()
        cursor = conexion.execute(
            "UPDATE vencimientos SET descripcion = ?, tipo = ?, fecha_vencimiento = ?, maquina_id = ?, "
            "observaciones = ?, resuelto = ? WHERE id = ?",
            (descripcion, tipo, str(fecha_vencimiento), maquina_id, observaciones, int(resuelto), vencimiento_id),
        )
        if cursor.rowcount == 0:
            raise NoEncontrado()
        return _obtener_vencimiento(conexion, vencimiento_id)


def eliminar_vencimiento(vencimiento_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM vencimientos WHERE id = ?", (vencimiento_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


# ---------- Contactos ----------

CAMPOS_CONTACTO = ("nombre", "rubro", "empresa", "telefono", "email", "notas")


def listar_contactos():
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            "SELECT * FROM contactos ORDER BY rubro, nombre COLLATE NOCASE"
        ).fetchall())


def agregar_contacto(datos: dict):
    with conectar() as conexion:
        cursor = conexion.execute(
            f"INSERT INTO contactos ({', '.join(CAMPOS_CONTACTO)}) VALUES (?, ?, ?, ?, ?, ?)",
            [datos[c] for c in CAMPOS_CONTACTO],
        )
        return dict(conexion.execute("SELECT * FROM contactos WHERE id = ?", (cursor.lastrowid,)).fetchone())


def editar_contacto(contacto_id, datos: dict):
    asignaciones = ", ".join(f"{c} = ?" for c in CAMPOS_CONTACTO)
    with conectar() as conexion:
        cursor = conexion.execute(
            f"UPDATE contactos SET {asignaciones} WHERE id = ?",
            [datos[c] for c in CAMPOS_CONTACTO] + [contacto_id],
        )
        if cursor.rowcount == 0:
            raise NoEncontrado()
        return dict(conexion.execute("SELECT * FROM contactos WHERE id = ?", (contacto_id,)).fetchone())


def eliminar_contacto(contacto_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM contactos WHERE id = ?", (contacto_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


# ---------- Service programado (planes por horas) ----------
#
# Un plan dice "hacer X cada N horas". Guardamos cuándo se hizo por última vez
# (ultima_horas). El próximo toca a las ultima_horas + cada_horas.
# "faltan" = próximo - horas actuales (negativo = ya se pasó).

SELECT_PLANES = """
    SELECT p.*, m.nombre AS maquina_nombre, m.horas_motor, m.horas_trilla, m.archivado AS maquina_archivada
    FROM planes_service p JOIN maquinas m ON m.id = p.maquina_id
"""


def _calcular_estado(plan: dict) -> dict:
    """Agrega al plan: horas_actuales, proximo, faltan y estado (ok / proximo / vencido)."""
    plan = dict(plan)
    actuales = plan["horas_motor"] if plan["medida"] == "motor" else (plan["horas_trilla"] or 0)
    plan["horas_actuales"] = actuales
    plan["proximo"] = plan["ultima_horas"] + plan["cada_horas"]
    plan["faltan"] = round(plan["proximo"] - actuales, 2)
    margen = plan["cada_horas"] * AVISO_SERVICE_PORCENTAJE / 100
    if plan["faltan"] < 0:
        plan["estado"] = "vencido"
    elif plan["faltan"] <= margen:
        plan["estado"] = "proximo"
    else:
        plan["estado"] = "ok"
    return plan


def listar_planes(maquina_id=None, solo_activos=True):
    """Planes con su estado calculado, del más urgente al menos urgente."""
    condiciones, valores = [], []
    if maquina_id is not None:
        condiciones.append("p.maquina_id = ?")
        valores.append(maquina_id)
    else:
        condiciones.append("m.archivado = 0")
    if solo_activos:
        condiciones.append("p.activo = 1")
    donde = " WHERE " + " AND ".join(condiciones)
    with conectar() as conexion:
        filas = conexion.execute(SELECT_PLANES + donde, valores).fetchall()
    planes = [_calcular_estado(f) for f in filas]
    return sorted(planes, key=lambda p: (not p["activo"], p["faltan"]))


def services_para_alertar():
    """Planes activos que ya se pasaron o están por cumplirse."""
    return [p for p in listar_planes() if p["estado"] != "ok"]


def _obtener_plan(conexion, plan_id):
    fila = conexion.execute(SELECT_PLANES + " WHERE p.id = ?", (plan_id,)).fetchone()
    return _calcular_estado(fila) if fila else None


def agregar_plan(maquina_id, nombre, cada_horas, medida="motor", ultima_horas=None, ultima_fecha=None, activo=True):
    """Crea un plan. Si no se dice cuándo se hizo el último, se toma "ahora" (horas actuales)."""
    with conectar() as conexion:
        maquina = _obtener_maquina(conexion, maquina_id)
        if maquina is None:
            raise MaquinaNoEncontrada()
        if ultima_horas is None:
            ultima_horas = maquina["horas_motor"] if medida == "motor" else (maquina["horas_trilla"] or 0)
        cursor = conexion.execute(
            "INSERT INTO planes_service (maquina_id, nombre, cada_horas, medida, ultima_horas, ultima_fecha, activo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (maquina_id, nombre, cada_horas, medida, ultima_horas,
             str(ultima_fecha) if ultima_fecha else None, int(activo)),
        )
        return _obtener_plan(conexion, cursor.lastrowid)


def editar_plan(plan_id, nombre, cada_horas, medida, ultima_horas, ultima_fecha, activo):
    with conectar() as conexion:
        plan = _obtener_plan(conexion, plan_id)
        if plan is None:
            raise NoEncontrado()
        if ultima_horas is None:
            ultima_horas = plan["ultima_horas"]
        conexion.execute(
            "UPDATE planes_service SET nombre = ?, cada_horas = ?, medida = ?, ultima_horas = ?, "
            "ultima_fecha = ?, activo = ? WHERE id = ?",
            (nombre, cada_horas, medida, ultima_horas, str(ultima_fecha) if ultima_fecha else None,
             int(activo), plan_id),
        )
        return _obtener_plan(conexion, plan_id)


def eliminar_plan(plan_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM planes_service WHERE id = ?", (plan_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado()


def _marcar_planes_hechos(conexion, maquina_id, plan_ids, fecha, horas_motor, horas_trilla):
    """Reinicia el contador de los planes indicados (usa una conexión ya abierta)."""
    for plan_id in plan_ids:
        plan = _obtener_plan(conexion, plan_id)
        if plan is None or plan["maquina_id"] != maquina_id:
            raise NoEncontrado(f"El plan {plan_id} no es de esta máquina.")
        horas = horas_motor if plan["medida"] == "motor" else horas_trilla
        conexion.execute(
            "UPDATE planes_service SET ultima_horas = ?, ultima_fecha = ? WHERE id = ?",
            (horas, str(fecha), plan_id),
        )
