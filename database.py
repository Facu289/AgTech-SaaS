import sqlite3
from contextlib import contextmanager
from pathlib import Path

# El archivo de la base de datos se crea en la misma carpeta que este archivo.
DB_PATH = Path(__file__).parent / "agroapp.db"


class InsumoNoEncontrado(Exception):
    """Se pidió un insumo que no existe."""


class StockInsuficiente(Exception):
    """Se intentó sacar más de lo que hay."""

    def __init__(self, disponible):
        super().__init__(f"Stock insuficiente: hay {disponible}")
        self.disponible = disponible


@contextmanager
def conectar():
    """Abre la base, guarda los cambios si todo salió bien y SIEMPRE la cierra.

    Si ocurre un error en el medio, NO se hace commit: ningún cambio queda a medias.
    """
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row  # Permite leer columnas por nombre.
    conexion.execute("PRAGMA foreign_keys = ON")  # Hace respetar las relaciones.
    try:
        yield conexion
        conexion.commit()
    finally:
        conexion.close()


def crear_tablas():
    """Crea las tablas si todavía no existen. Se puede llamar muchas veces."""
    with conectar() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS insumos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                categoria TEXT    NOT NULL,
                unidad    TEXT    NOT NULL,
                cantidad  REAL    NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
                creado_en TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS notas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                texto     TEXT    NOT NULL,
                hecha     INTEGER NOT NULL DEFAULT 0 CHECK (hecha IN (0, 1)),
                creada_en TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS movimientos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                insumo_id INTEGER NOT NULL REFERENCES insumos(id),
                tipo      TEXT    NOT NULL CHECK (tipo IN ('entrada', 'salida')),
                cantidad  REAL    NOT NULL CHECK (cantidad > 0),
                motivo    TEXT    NOT NULL DEFAULT '',
                fecha     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        # Una sola vez: a los insumos cargados ANTES de existir esta tabla
        # les registramos su cantidad actual como "stock inicial".
        conexion.execute(
            """
            INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo)
            SELECT id, 'entrada', cantidad, 'stock inicial'
            FROM insumos
            WHERE cantidad > 0
              AND id NOT IN (SELECT insumo_id FROM movimientos)
            """
        )


# ---------- Insumos ----------

def agregar_insumo(nombre, categoria, unidad, cantidad):
    """Guarda un insumo nuevo (y su stock inicial) y lo devuelve como diccionario."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO insumos (nombre, categoria, unidad, cantidad) VALUES (?, ?, ?, ?)",
            (nombre, categoria, unidad, cantidad),
        )
        insumo_id = cursor.lastrowid
        if cantidad > 0:
            conexion.execute(
                "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo) "
                "VALUES (?, 'entrada', ?, 'stock inicial')",
                (insumo_id, cantidad),
            )
        return _obtener_insumo(conexion, insumo_id)


def _obtener_insumo(conexion, insumo_id):
    """Busca un insumo por id usando una conexión ya abierta. Devuelve dict o None."""
    fila = conexion.execute(
        "SELECT id, nombre, categoria, unidad, cantidad FROM insumos WHERE id = ?",
        (insumo_id,),
    ).fetchone()
    return dict(fila) if fila else None


def listar_insumos():
    """Devuelve todos los insumos ordenados por categoría y nombre."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT id, nombre, categoria, unidad, cantidad FROM insumos ORDER BY categoria, nombre"
        ).fetchall()
        return [dict(fila) for fila in filas]


# ---------- Movimientos de stock ----------

def registrar_movimiento(insumo_id, tipo, cantidad, motivo=""):
    """Registra una entrada o salida y actualiza el stock, TODO JUNTO.

    Devuelve el insumo con la cantidad actualizada.
    Lanza InsumoNoEncontrado o StockInsuficiente si no se puede.
    """
    with conectar() as conexion:
        insumo = _obtener_insumo(conexion, insumo_id)
        if insumo is None:
            raise InsumoNoEncontrado()

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
        return [dict(fila) for fila in filas]


# ---------- Notas ----------

def agregar_nota(texto):
    """Guarda una nota nueva y devuelve su id."""
    with conectar() as conexion:
        cursor = conexion.execute("INSERT INTO notas (texto) VALUES (?)", (texto,))
        return cursor.lastrowid


def listar_notas_pendientes():
    """Devuelve las notas que todavía no se marcaron como hechas."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT id, texto, creada_en FROM notas WHERE hecha = 0 ORDER BY id"
        ).fetchall()
        return [dict(fila) for fila in filas]


def marcar_nota_hecha(nota_id):
    """Marca una nota como hecha. Devuelve True si existía y estaba pendiente."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE notas SET hecha = 1 WHERE id = ? AND hecha = 0", (nota_id,)
        )
        return cursor.rowcount == 1