import sqlite3
from contextlib import contextmanager
from pathlib import Path

# El archivo de la base de datos se crea en la misma carpeta que este archivo.
DB_PATH = Path(__file__).parent / "agroapp.db"


@contextmanager
def conectar():
    """Abre la base, guarda los cambios si todo salió bien y SIEMPRE la cierra."""
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row  # Permite leer columnas por nombre.
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


def agregar_insumo(nombre, categoria, unidad, cantidad):
    """Guarda un insumo nuevo y lo devuelve como diccionario."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO insumos (nombre, categoria, unidad, cantidad) VALUES (?, ?, ?, ?)",
            (nombre, categoria, unidad, cantidad),
        )
        fila = conexion.execute(
            "SELECT id, nombre, categoria, unidad, cantidad FROM insumos WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(fila)


def listar_insumos():
    """Devuelve todos los insumos ordenados por categoría y nombre."""
    with conectar() as conexion:
        filas = conexion.execute(
            "SELECT id, nombre, categoria, unidad, cantidad FROM insumos ORDER BY categoria, nombre"
        ).fetchall()
        return [dict(fila) for fila in filas]