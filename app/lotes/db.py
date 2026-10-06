"""SQL de lotes, cultivos, campañas y qué se sembró en cada lote.

La geometría (el polígono) se guarda como TEXTO JSON en la base y se devuelve como
diccionario: quien usa estas funciones nunca ve el texto.
"""
import json

from app.nucleo.database import NoEncontrado, TieneHistorial, conectar, filas_a_dicts


class LoteNoEncontrado(NoEncontrado):
    """Se pidió un lote que no existe."""


CAMPOS_LOTE = ("nombre", "geometria", "hectareas", "observaciones")


def _a_dict(fila):
    lote = dict(fila)
    lote["geometria"] = json.loads(lote["geometria"]) if lote["geometria"] else None
    return lote


def _valores(datos: dict):
    valores = dict(datos)
    valores["geometria"] = json.dumps(datos["geometria"]) if datos["geometria"] else None
    return [valores[c] for c in CAMPOS_LOTE]


def _obtener(conexion, lote_id):
    fila = conexion.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
    if fila is None:
        raise LoteNoEncontrado()
    return _a_dict(fila)


def listar_lotes(incluir_archivados=False):
    condicion = "" if incluir_archivados else " WHERE archivado = 0"
    with conectar() as conexion:
        filas = conexion.execute(f"SELECT * FROM lotes{condicion} ORDER BY nombre COLLATE NOCASE").fetchall()
        return [_a_dict(fila) for fila in filas]


def obtener_lote(lote_id):
    with conectar() as conexion:
        return _obtener(conexion, lote_id)


def agregar_lote(datos: dict):
    with conectar() as conexion:
        cursor = conexion.execute(
            f"INSERT INTO lotes ({', '.join(CAMPOS_LOTE)}) VALUES (?, ?, ?, ?)", _valores(datos)
        )
        return _obtener(conexion, cursor.lastrowid)


def editar_lote(lote_id, datos: dict):
    asignaciones = ", ".join(f"{c} = ?" for c in CAMPOS_LOTE)
    with conectar() as conexion:
        cursor = conexion.execute(
            f"UPDATE lotes SET {asignaciones}, actualizado_en = datetime('now', 'localtime') WHERE id = ?",
            _valores(datos) + [lote_id],
        )
        if cursor.rowcount == 0:
            raise LoteNoEncontrado()
        return _obtener(conexion, lote_id)


def archivar_lote(lote_id, archivado=True):
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE lotes SET archivado = ?, actualizado_en = datetime('now', 'localtime') WHERE id = ?",
            (int(archivado), lote_id),
        )
        if cursor.rowcount == 0:
            raise LoteNoEncontrado()
        return _obtener(conexion, lote_id)


def eliminar_lote(lote_id):
    """Borra un lote SOLO si no tiene cultivos cargados. Si tiene historial, hay que archivarlo."""
    with conectar() as conexion:
        _obtener(conexion, lote_id)  # LoteNoEncontrado si no existe.
        if conexion.execute("SELECT 1 FROM lote_cultivos WHERE lote_id = ? LIMIT 1", (lote_id,)).fetchone():
            raise TieneHistorial()
        conexion.execute("DELETE FROM lotes WHERE id = ?", (lote_id,))


# ---------- Cultivos (soja, maíz... con su color) ----------

def listar_cultivos():
    """Cada cultivo con cuántas veces se usó (si se usó, no se puede borrar)."""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM lote_cultivos WHERE cultivo_id = c.id) AS usos
            FROM cultivos c ORDER BY c.nombre COLLATE NOCASE
            """
        ).fetchall())


def _obtener_fila(conexion, tabla, fila_id):
    fila = conexion.execute(f"SELECT * FROM {tabla} WHERE id = ?", (fila_id,)).fetchone()
    if fila is None:
        raise NoEncontrado()
    return dict(fila)


def agregar_cultivo(nombre, color):
    with conectar() as conexion:
        cursor = conexion.execute("INSERT INTO cultivos (nombre, color) VALUES (?, ?)", (nombre, color))
        return _obtener_fila(conexion, "cultivos", cursor.lastrowid)


def editar_cultivo(cultivo_id, nombre, color):
    with conectar() as conexion:
        _obtener_fila(conexion, "cultivos", cultivo_id)
        conexion.execute("UPDATE cultivos SET nombre = ?, color = ? WHERE id = ?", (nombre, color, cultivo_id))
        return _obtener_fila(conexion, "cultivos", cultivo_id)


def eliminar_cultivo(cultivo_id):
    with conectar() as conexion:
        _obtener_fila(conexion, "cultivos", cultivo_id)
        if conexion.execute("SELECT 1 FROM lote_cultivos WHERE cultivo_id = ? LIMIT 1", (cultivo_id,)).fetchone():
            raise TieneHistorial()
        conexion.execute("DELETE FROM cultivos WHERE id = ?", (cultivo_id,))


# ---------- Campañas ("2026/27") ----------

def listar_campanias():
    """De la más nueva a la más vieja ("2026/27" antes que "2025/26"), con cuántos lotes tienen cultivo."""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM lote_cultivos WHERE campania_id = c.id) AS usos
            FROM campanias c ORDER BY c.nombre COLLATE NOCASE DESC
            """
        ).fetchall())


def agregar_campania(nombre):
    with conectar() as conexion:
        cursor = conexion.execute("INSERT INTO campanias (nombre) VALUES (?)", (nombre,))
        return _obtener_fila(conexion, "campanias", cursor.lastrowid)


def editar_campania(campania_id, nombre):
    with conectar() as conexion:
        _obtener_fila(conexion, "campanias", campania_id)
        conexion.execute("UPDATE campanias SET nombre = ? WHERE id = ?", (nombre, campania_id))
        return _obtener_fila(conexion, "campanias", campania_id)


def eliminar_campania(campania_id):
    with conectar() as conexion:
        _obtener_fila(conexion, "campanias", campania_id)
        if conexion.execute("SELECT 1 FROM lote_cultivos WHERE campania_id = ? LIMIT 1", (campania_id,)).fetchone():
            raise TieneHistorial()
        conexion.execute("DELETE FROM campanias WHERE id = ?", (campania_id,))


# ---------- Cultivo de cada lote en cada campaña ----------

SELECT_LOTE_CULTIVOS = """
    SELECT lc.*, c.nombre AS cultivo, c.color, ca.nombre AS campania, l.nombre AS lote,
           l.hectareas AS hectareas_lote
    FROM lote_cultivos lc
    JOIN cultivos c ON c.id = lc.cultivo_id
    JOIN campanias ca ON ca.id = lc.campania_id
    JOIN lotes l ON l.id = lc.lote_id
"""

# Primera antes que segunda: 'primera' < 'segunda' en orden alfabético.
ORDEN_LOTE_CULTIVOS = " ORDER BY ca.nombre COLLATE NOCASE DESC, lc.ciclo"

CAMPOS_LOTE_CULTIVO = (
    "campania_id", "cultivo_id", "ciclo", "variedad", "fecha_siembra", "fecha_cosecha", "hectareas", "rinde",
    "observaciones",
)


def listar_lote_cultivos(lote_id=None, campania_id=None):
    condiciones, valores = [], []
    if lote_id is not None:
        condiciones.append("lc.lote_id = ?")
        valores.append(lote_id)
    if campania_id is not None:
        condiciones.append("lc.campania_id = ?")
        valores.append(campania_id)
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as conexion:
        return filas_a_dicts(conexion.execute(SELECT_LOTE_CULTIVOS + donde + ORDEN_LOTE_CULTIVOS, valores).fetchall())


def _obtener_lote_cultivo(conexion, fila_id):
    fila = conexion.execute(SELECT_LOTE_CULTIVOS + " WHERE lc.id = ?", (fila_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("No existe ese cultivo del lote (puede que ya se haya borrado).")
    return dict(fila)


def agregar_lote_cultivo(lote_id, datos: dict):
    with conectar() as conexion:
        _obtener(conexion, lote_id)
        cursor = conexion.execute(
            f"INSERT INTO lote_cultivos (lote_id, {', '.join(CAMPOS_LOTE_CULTIVO)}) "
            f"VALUES (?, {', '.join('?' for _ in CAMPOS_LOTE_CULTIVO)})",
            [lote_id] + [datos[c] for c in CAMPOS_LOTE_CULTIVO],
        )
        return _obtener_lote_cultivo(conexion, cursor.lastrowid)


def editar_lote_cultivo(fila_id, datos: dict):
    asignaciones = ", ".join(f"{c} = ?" for c in CAMPOS_LOTE_CULTIVO)
    with conectar() as conexion:
        _obtener_lote_cultivo(conexion, fila_id)
        conexion.execute(
            f"UPDATE lote_cultivos SET {asignaciones} WHERE id = ?",
            [datos[c] for c in CAMPOS_LOTE_CULTIVO] + [fila_id],
        )
        return _obtener_lote_cultivo(conexion, fila_id)


def eliminar_lote_cultivo(fila_id):
    with conectar() as conexion:
        cursor = conexion.execute("DELETE FROM lote_cultivos WHERE id = ?", (fila_id,))
        if cursor.rowcount == 0:
            raise NoEncontrado("No existe ese cultivo del lote (puede que ya se haya borrado).")
