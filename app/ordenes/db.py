"""SQL de órdenes de trabajo.

Cómo se mueve el stock:
- Al cargar o editar una orden (PENDIENTE) no se toca el stock.
- Al marcarla REALIZADA, cada producto sale del stock como una SALIDA en Movimientos
  (con movimientos.orden_id = la orden). Todo en una transacción: si a un producto no le
  alcanza, no se descuenta NINGUNO.
- "Volver a pendiente" devuelve el stock con ENTRADAS (no se borra el historial).
"""
import re
from datetime import datetime

from app.nucleo.database import NoEncontrado, TieneHistorial, conectar, filas_a_dicts


class OrdenNoEncontrada(NoEncontrado):
    """Se pidió una orden que no existe."""


class EstadoInvalido(Exception):
    """La orden no está en el estado que hace falta (ej: editar una orden ya realizada)."""


class FaltaStock(Exception):
    """Al realizar la orden, a uno o más productos no les alcanza el stock."""

    def __init__(self, faltantes):
        super().__init__("No alcanza el stock para realizar la orden.")
        self.faltantes = faltantes


CAMPOS_ORDEN = (
    "numero", "campania_id", "campo", "tarea", "maquina", "operarios", "fecha_emision", "estado_lote",
    "cultivo", "caldo_ha", "tancadas", "descripcion",
)

SELECT_ORDENES = """
    SELECT o.*, c.nombre AS campania,
           (SELECT COALESCE(SUM(hectareas), 0) FROM orden_lotes WHERE orden_id = o.id) AS hectareas
    FROM ordenes_trabajo o
    LEFT JOIN campanias c ON c.id = o.campania_id
"""


def _completar(conexion, ordenes):
    """A cada orden le agrega sus "lotes" y sus "productos" (con nombre, unidad y stock actual)."""
    ids = [o["id"] for o in ordenes]
    if not ids:
        return ordenes
    marcas = ", ".join("?" for _ in ids)
    lotes = conexion.execute(
        f"SELECT * FROM orden_lotes WHERE orden_id IN ({marcas}) ORDER BY id", ids
    ).fetchall()
    productos = conexion.execute(
        f"""
        SELECT p.*, i.nombre AS insumo, i.unidad, i.categoria, i.cantidad AS stock, i.archivado
        FROM orden_productos p JOIN insumos i ON i.id = p.insumo_id
        WHERE p.orden_id IN ({marcas}) ORDER BY p.id
        """,
        ids,
    ).fetchall()
    por_id = {o["id"]: o for o in ordenes}
    for orden in ordenes:
        orden["lotes"], orden["productos"] = [], []
    for fila in lotes:
        por_id[fila["orden_id"]]["lotes"].append(dict(fila))
    for fila in productos:
        por_id[fila["orden_id"]]["productos"].append(dict(fila))
    return ordenes


def _obtener(conexion, orden_id):
    fila = conexion.execute(SELECT_ORDENES + " WHERE o.id = ?", (orden_id,)).fetchone()
    if fila is None:
        raise OrdenNoEncontrada()
    return _completar(conexion, [dict(fila)])[0]


def obtener_orden(orden_id):
    with conectar() as conexion:
        return _obtener(conexion, orden_id)


def listar_ordenes(estado=None, campania_id=None):
    """Las órdenes, de la más nueva a la más vieja."""
    condiciones, valores = [], []
    if estado:
        condiciones.append("o.estado = ?")
        valores.append(estado)
    if campania_id is not None:
        condiciones.append("o.campania_id = ?")
        valores.append(campania_id)
    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as conexion:
        filas = conexion.execute(
            SELECT_ORDENES + donde + " ORDER BY o.fecha_emision DESC, o.id DESC", valores
        ).fetchall()
        return _completar(conexion, filas_a_dicts(filas))


def _guardar_detalle(conexion, orden_id, lotes, productos):
    """Reemplaza los lotes y productos de la orden por los nuevos."""
    conexion.execute("DELETE FROM orden_lotes WHERE orden_id = ?", (orden_id,))
    conexion.execute("DELETE FROM orden_productos WHERE orden_id = ?", (orden_id,))
    conexion.executemany(
        "INSERT INTO orden_lotes (orden_id, lote, hectareas) VALUES (?, ?, ?)",
        [(orden_id, l["lote"], l["hectareas"]) for l in lotes],
    )
    conexion.executemany(
        "INSERT INTO orden_productos (orden_id, insumo_id, cantidad_total) VALUES (?, ?, ?)",
        [(orden_id, p["insumo_id"], p["cantidad_total"]) for p in productos],
    )


def agregar_orden(datos: dict):
    with conectar() as conexion:
        cursor = conexion.execute(
            f"INSERT INTO ordenes_trabajo ({', '.join(CAMPOS_ORDEN)}) "
            f"VALUES ({', '.join('?' for _ in CAMPOS_ORDEN)})",
            [datos[c] for c in CAMPOS_ORDEN],
        )
        _guardar_detalle(conexion, cursor.lastrowid, datos["lotes"], datos["productos"])
        return _obtener(conexion, cursor.lastrowid)


def editar_orden(orden_id, datos: dict):
    """Solo se edita una orden PENDIENTE (una realizada ya movió el stock)."""
    asignaciones = ", ".join(f"{c} = ?" for c in CAMPOS_ORDEN)
    with conectar() as conexion:
        if _obtener(conexion, orden_id)["estado"] != "pendiente":
            raise EstadoInvalido("Solo se puede editar una orden pendiente: si ya se realizó, volvela a pendiente.")
        conexion.execute(
            f"UPDATE ordenes_trabajo SET {asignaciones}, actualizado_en = datetime('now', 'localtime') WHERE id = ?",
            [datos[c] for c in CAMPOS_ORDEN] + [orden_id],
        )
        _guardar_detalle(conexion, orden_id, datos["lotes"], datos["productos"])
        return _obtener(conexion, orden_id)


def totales_por_insumo(orden):
    """{insumo_id: {"insumo", "unidad", "necesita", "hay", "archivado"}}: suma si un producto se repite."""
    totales = {}
    for producto in orden["productos"]:
        total = totales.setdefault(producto["insumo_id"], {
            "insumo_id": producto["insumo_id"], "insumo": producto["insumo"], "unidad": producto["unidad"],
            "necesita": 0.0, "hay": producto["stock"], "archivado": bool(producto["archivado"]),
        })
        total["necesita"] += producto["cantidad_total"]
    return totales


def faltantes(orden):
    """Los productos a los que no les alcanza el stock (o que están archivados)."""
    return [t for t in totales_por_insumo(orden).values() if t["archivado"] or t["necesita"] > t["hay"] + 1e-9]


def describir(orden):
    """'OT 1-033 · LM · Lotes 31+32, 37' (el motivo de los movimientos de stock)."""
    partes = [f"OT {orden['numero']}" if orden["numero"] else f"Orden de trabajo #{orden['id']}"]
    if orden["campo"]:
        partes.append(orden["campo"])
    if orden["lotes"]:
        partes.append("Lotes " + ", ".join(l["lote"] for l in orden["lotes"]))
    return " · ".join(partes)[:200]


def _cambiar_estado(conexion, orden_id, estado, fecha_realizacion=None):
    conexion.execute(
        "UPDATE ordenes_trabajo SET estado = ?, fecha_realizacion = ?, actualizado_en = datetime('now', 'localtime') "
        "WHERE id = ?",
        (estado, fecha_realizacion, orden_id),
    )


def realizar_orden(orden_id, fecha_realizacion):
    """Marca la orden como realizada y descuenta del stock TODOS sus productos (o ninguno)."""
    momento = f"{fecha_realizacion} {datetime.now():%H:%M:%S}"
    with conectar() as conexion:
        orden = _obtener(conexion, orden_id)
        if orden["estado"] != "pendiente":
            raise EstadoInvalido("Solo se puede realizar una orden pendiente.")
        if not orden["productos"]:
            raise EstadoInvalido("La orden no tiene productos: no hay nada para descontar del stock.")
        faltan = faltantes(orden)
        if faltan:
            raise FaltaStock(faltan)
        motivo = describir(orden)
        for total in totales_por_insumo(orden).values():
            conexion.execute(
                "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo, fecha, orden_id) VALUES (?, 'salida', ?, ?, ?, ?)",
                (total["insumo_id"], total["necesita"], motivo, momento, orden_id),
            )
            conexion.execute(
                "UPDATE insumos SET cantidad = cantidad - ? WHERE id = ?", (total["necesita"], total["insumo_id"])
            )
        _cambiar_estado(conexion, orden_id, "realizada", str(fecha_realizacion))
        return _obtener(conexion, orden_id)


def volver_a_pendiente(orden_id):
    """Deshace una orden realizada: devuelve al stock lo que se descontó (con ENTRADAS)."""
    with conectar() as conexion:
        orden = _obtener(conexion, orden_id)
        if orden["estado"] != "realizada":
            raise EstadoInvalido("Solo se puede volver a pendiente una orden realizada.")
        # Se devuelve lo que REALMENTE salió por esta orden (por si algo cambió desde entonces).
        salidas = conexion.execute(
            "SELECT insumo_id, SUM(CASE WHEN tipo = 'salida' THEN cantidad ELSE -cantidad END) AS neto "
            "FROM movimientos WHERE orden_id = ? GROUP BY insumo_id",
            (orden_id,),
        ).fetchall()
        motivo = f"Devolución: {describir(orden)} volvió a pendiente"[:200]
        for insumo_id, neto in salidas:
            if neto <= 0:
                continue
            conexion.execute(
                "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo, orden_id) VALUES (?, 'entrada', ?, ?, ?)",
                (insumo_id, neto, motivo, orden_id),
            )
            conexion.execute("UPDATE insumos SET cantidad = cantidad + ? WHERE id = ?", (neto, insumo_id))
        _cambiar_estado(conexion, orden_id, "pendiente")
        return _obtener(conexion, orden_id)


def anular_orden(orden_id, anulada=True):
    """Anula una orden pendiente (no se hizo), o la reactiva. Una realizada primero vuelve a pendiente."""
    with conectar() as conexion:
        orden = _obtener(conexion, orden_id)
        if anulada and orden["estado"] != "pendiente":
            raise EstadoInvalido("Solo se puede anular una orden pendiente: si ya se realizó, volvela a pendiente.")
        if not anulada and orden["estado"] != "anulada":
            raise EstadoInvalido("La orden no está anulada.")
        _cambiar_estado(conexion, orden_id, "anulada" if anulada else "pendiente")
        return _obtener(conexion, orden_id)


def eliminar_orden(orden_id):
    """Borra una orden SOLO si nunca movió stock. Si ya movió, queda en el historial (anulala)."""
    with conectar() as conexion:
        _obtener(conexion, orden_id)
        if conexion.execute("SELECT 1 FROM movimientos WHERE orden_id = ? LIMIT 1", (orden_id,)).fetchone():
            raise TieneHistorial()
        conexion.execute("DELETE FROM orden_lotes WHERE orden_id = ?", (orden_id,))
        conexion.execute("DELETE FROM orden_productos WHERE orden_id = ?", (orden_id,))
        conexion.execute("DELETE FROM ordenes_trabajo WHERE id = ?", (orden_id,))


def siguiente_numero():
    """Propone el número de la próxima orden: "1-033" → "1-034" (respeta los ceros). Vacío si no hay."""
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT numero FROM ordenes_trabajo WHERE numero != '' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if fila is None:
        return ""
    coincidencia = re.search(r"(\d+)(\D*)$", fila["numero"])
    if not coincidencia:
        return ""
    digitos = coincidencia.group(1)
    nuevo = str(int(digitos) + 1).zfill(len(digitos))
    return fila["numero"][: coincidencia.start(1)] + nuevo + coincidencia.group(2)
