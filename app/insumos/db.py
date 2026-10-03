"""SQL de insumos (y repuestos) y de movimientos de stock."""
from app.nucleo.database import Archivado, NoEncontrado, TieneHistorial, conectar, filas_a_dicts
from app.nucleo.opciones import hoja_de


class InsumoNoEncontrado(NoEncontrado):
    """Se pidió un insumo que no existe."""


class StockInsuficiente(Exception):
    """Se intentó sacar más de lo que hay."""

    def __init__(self, disponible):
        super().__init__(f"Stock insuficiente: hay {disponible}")
        self.disponible = disponible


# ---------- Insumos ----------

# La misma consulta sirve para listar y para buscar uno (así devuelven lo mismo).
SELECT_INSUMOS = """
    SELECT i.id, i.nombre, i.categoria, i.subcategoria, i.unidad, i.cantidad,
           i.stock_minimo, i.archivado,
           EXISTS (SELECT 1 FROM movimientos mv WHERE mv.insumo_id = i.id) AS tiene_movimientos
    FROM insumos i
"""


def _agregar_maquinas(conexion, insumos: list) -> list:
    """A cada insumo le agrega "maquinas": [{"id": 1, "nombre": "Tractor JD"}, ...]
    y "hoja": en qué página se ve ('insumos', 'quimicos' o 'repuestos').

    Se hace con UNA consulta para todos (no una por insumo) y se reparte en Python.
    """
    por_insumo = {insumo["id"]: [] for insumo in insumos}
    filas = conexion.execute(
        "SELECT im.insumo_id, m.id, m.nombre FROM insumo_maquinas im "
        "JOIN maquinas m ON m.id = im.maquina_id ORDER BY m.nombre COLLATE NOCASE"
    ).fetchall()
    for insumo_id, maquina_id, nombre in filas:
        if insumo_id in por_insumo:
            por_insumo[insumo_id].append({"id": maquina_id, "nombre": nombre})
    for insumo in insumos:
        insumo["maquinas"] = por_insumo[insumo["id"]]
        insumo["hoja"] = hoja_de(insumo["categoria"])
    return insumos


def _guardar_maquinas(conexion, insumo_id, maquina_ids):
    """Reemplaza las máquinas de un insumo: borra las que tenía y guarda las nuevas."""
    conexion.execute("DELETE FROM insumo_maquinas WHERE insumo_id = ?", (insumo_id,))
    conexion.executemany(
        "INSERT INTO insumo_maquinas (insumo_id, maquina_id) VALUES (?, ?)",
        [(insumo_id, maquina_id) for maquina_id in dict.fromkeys(maquina_ids)],  # Sin repetidos.
    )


def _obtener_insumo(conexion, insumo_id):
    """Busca un insumo por id usando una conexión ya abierta. Devuelve dict o None."""
    fila = conexion.execute(SELECT_INSUMOS + " WHERE i.id = ?", (insumo_id,)).fetchone()
    return _agregar_maquinas(conexion, [dict(fila)])[0] if fila else None


def obtener_insumo(insumo_id):
    with conectar() as conexion:
        return _obtener_insumo(conexion, insumo_id)


def listar_insumos(incluir_archivados=False):
    """Devuelve los insumos ordenados por categoría y nombre."""
    condicion = "" if incluir_archivados else " WHERE i.archivado = 0"
    with conectar() as conexion:
        filas = conexion.execute(
            SELECT_INSUMOS + condicion + " ORDER BY i.categoria, i.nombre"
        ).fetchall()
        return _agregar_maquinas(conexion, filas_a_dicts(filas))


def agregar_insumo(nombre, categoria, unidad, cantidad=0, subcategoria="", maquina_ids=(), stock_minimo=0):
    """Guarda un insumo nuevo (su stock inicial y sus máquinas) y lo devuelve como diccionario."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO insumos (nombre, categoria, subcategoria, unidad, cantidad, stock_minimo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, categoria, subcategoria, unidad, cantidad, stock_minimo),
        )
        insumo_id = cursor.lastrowid
        _guardar_maquinas(conexion, insumo_id, maquina_ids)
        if cantidad > 0:
            conexion.execute(
                "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo) "
                "VALUES (?, 'entrada', ?, 'stock inicial')",
                (insumo_id, cantidad),
            )
        return _obtener_insumo(conexion, insumo_id)


def editar_insumo(insumo_id, nombre, categoria, subcategoria, unidad, maquina_ids, stock_minimo):
    """Cambia los datos de un insumo (NO la cantidad: eso se hace con movimientos)."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE insumos SET nombre = ?, categoria = ?, subcategoria = ?, unidad = ?, "
            "stock_minimo = ? WHERE id = ?",
            (nombre, categoria, subcategoria, unidad, stock_minimo, insumo_id),
        )
        if cursor.rowcount == 0:
            raise InsumoNoEncontrado()
        _guardar_maquinas(conexion, insumo_id, maquina_ids)
        return _obtener_insumo(conexion, insumo_id)


def listar_repuestos_de_maquina(maquina_id):
    """Repuestos (no archivados) que sirven para una máquina."""
    return [
        insumo for insumo in listar_insumos()
        if any(maquina["id"] == maquina_id for maquina in insumo["maquinas"])
    ]


def archivar_insumo(insumo_id, archivado=True):
    """Archiva (o desarchiva) un insumo: deja de aparecer, pero se conserva su historial."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE insumos SET archivado = ? WHERE id = ?", (int(archivado), insumo_id)
        )
        if cursor.rowcount == 0:
            raise InsumoNoEncontrado()
        return _obtener_insumo(conexion, insumo_id)


def eliminar_insumo(insumo_id):
    """Borra un insumo SOLO si nunca tuvo movimientos. Si tiene, hay que archivarlo."""
    with conectar() as conexion:
        insumo = _obtener_insumo(conexion, insumo_id)
        if insumo is None:
            raise InsumoNoEncontrado()
        if insumo["tiene_movimientos"]:
            raise TieneHistorial()
        conexion.execute("DELETE FROM insumo_maquinas WHERE insumo_id = ?", (insumo_id,))
        conexion.execute("DELETE FROM insumos WHERE id = ?", (insumo_id,))


# ---------- Movimientos de stock ----------

def registrar_movimiento(insumo_id, tipo, cantidad, motivo=""):
    """Registra una entrada o salida y actualiza el stock, TODO JUNTO.

    Devuelve el insumo con la cantidad actualizada.
    Lanza InsumoNoEncontrado, Archivado o StockInsuficiente si no se puede.
    """
    with conectar() as conexion:
        insumo = _obtener_insumo(conexion, insumo_id)
        if insumo is None:
            raise InsumoNoEncontrado()
        if insumo["archivado"]:
            raise Archivado()

        if tipo == "entrada":
            nueva_cantidad = insumo["cantidad"] + cantidad
        else:
            nueva_cantidad = insumo["cantidad"] - cantidad
            if nueva_cantidad < 0:
                raise StockInsuficiente(insumo["cantidad"])

        conexion.execute(
            "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo) VALUES (?, ?, ?, ?)",
            (insumo_id, tipo, cantidad, motivo),
        )
        conexion.execute(
            "UPDATE insumos SET cantidad = ? WHERE id = ?",
            (nueva_cantidad, insumo_id),
        )
        return _obtener_insumo(conexion, insumo_id)


def listar_movimientos(insumo_id):
    """Devuelve el historial de movimientos de un insumo, del más nuevo al más viejo."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT id, insumo_id, tipo, cantidad, motivo, fecha FROM movimientos "
            "WHERE insumo_id = ? ORDER BY id DESC",
            (insumo_id,),
        ).fetchall()
        return filas_a_dicts(filas)


def buscar_movimientos(insumo_id=None, tipo=None, categoria=None, desde=None, hasta=None, texto=None, limite=500):
    """Historial de TODOS los insumos con filtros opcionales (el más nuevo primero).

    Los filtros se arman con "?" (nunca pegando texto en el SQL) para evitar inyección SQL.
    """
    condiciones, valores = [], []
    if insumo_id is not None:
        condiciones.append("mv.insumo_id = ?")
        valores.append(insumo_id)
    if tipo:
        condiciones.append("mv.tipo = ?")
        valores.append(tipo)
    if categoria:
        condiciones.append("i.categoria = ?")
        valores.append(categoria)
    if desde:
        condiciones.append("date(mv.fecha) >= ?")
        valores.append(str(desde))
    if hasta:
        condiciones.append("date(mv.fecha) <= ?")
        valores.append(str(hasta))
    if texto:
        condiciones.append("(i.nombre LIKE ? OR mv.motivo LIKE ?)")
        valores += [f"%{texto}%", f"%{texto}%"]

    donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT mv.id, mv.insumo_id, i.nombre AS insumo_nombre, i.categoria, i.unidad, "
            "mv.tipo, mv.cantidad, mv.motivo, mv.fecha "
            "FROM movimientos mv JOIN insumos i ON i.id = mv.insumo_id"
            + donde + " ORDER BY mv.id DESC LIMIT ?",
            (*valores, limite),
        ).fetchall()
        return filas_a_dicts(filas)
