"""Conexión a SQLite, errores comunes y migraciones (la estructura de la base).

El SQL de cada área está en su carpeta: app/insumos/db.py, app/maquinaria/db.py, etc.
Estos archivos NO saben nada de HTTP ni de Telegram: si algo no se puede hacer,
lanzan una excepción y quien los llamó decide qué mostrar.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Carpeta raíz del proyecto (agroapp/). Este archivo está en agroapp/app/nucleo/.
CARPETA_PROYECTO = Path(__file__).resolve().parents[2]

# La base vive en agroapp/datos/. (Los tests usan otra con la variable AGROAPP_DB).
DB_PATH = Path(os.getenv("AGROAPP_DB", CARPETA_PROYECTO / "datos" / "agroapp.db"))


class UbicacionVieja(Exception):
    """La base sigue en la raíz del proyecto (antes de reorganizar en carpetas)."""


def verificar_ubicacion():
    """Evita arrancar con una base VACÍA si todavía no se movió la vieja a datos/."""
    vieja = CARPETA_PROYECTO / "agroapp.db"
    if not DB_PATH.exists() and vieja.exists() and "AGROAPP_DB" not in os.environ:
        raise UbicacionVieja(
            f"Tu base de datos sigue en {vieja}. Corré reorganizar.ps1 para moverla a la carpeta datos/."
        )


# ---------- Errores ----------

class NoEncontrado(Exception):
    """Se pidió algo (insumo, máquina, animal...) que no existe."""


class TieneHistorial(Exception):
    """No se puede eliminar porque tiene datos asociados (hay que archivarlo)."""


class Archivado(Exception):
    """Se intentó usar algo que está archivado."""


# ---------- Conexión ----------

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


def filas_a_dicts(filas):
    return [dict(fila) for fila in filas]


# ---------- Tablas y migraciones ----------
#
# ¿Qué es una migración? Un cambio en la ESTRUCTURA de la base (agregar una
# tabla o una columna) que se aplica UNA sola vez.
# SQLite guarda un número, "user_version", que empieza en 0. Cada migración
# de la lista tiene un número (su posición + 1). Al arrancar, se aplican las
# que faltan, en orden, y se actualiza user_version.
# REGLA: nunca modificar una migración ya aplicada; si hace falta otro cambio,
# se agrega una NUEVA al final de la lista.

MIGRACIONES = [
    # 1) Maquinaria
    [
        """
        CREATE TABLE maquinas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            tipo          TEXT    NOT NULL,
            marca         TEXT    NOT NULL DEFAULT '',
            modelo        TEXT    NOT NULL DEFAULT '',
            anio          INTEGER,
            numero_serie  TEXT    NOT NULL DEFAULT '',
            patente       TEXT    NOT NULL DEFAULT '',
            horas_motor   REAL    NOT NULL DEFAULT 0 CHECK (horas_motor >= 0),
            horas_trilla  REAL    CHECK (horas_trilla IS NULL OR horas_trilla >= 0),
            observaciones TEXT    NOT NULL DEFAULT '',
            archivado     INTEGER NOT NULL DEFAULT 0 CHECK (archivado IN (0, 1)),
            creado_en     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE mantenimientos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            maquina_id  INTEGER NOT NULL REFERENCES maquinas(id),
            fecha       TEXT    NOT NULL,
            tipo        TEXT    NOT NULL CHECK (tipo IN ('service', 'arreglo')),
            horas       REAL    CHECK (horas IS NULL OR horas >= 0),
            descripcion TEXT    NOT NULL,
            costo       REAL    CHECK (costo IS NULL OR costo >= 0),
            creado_en   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE trabajos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            maquina_id    INTEGER NOT NULL REFERENCES maquinas(id),
            fecha         TEXT    NOT NULL,
            tipo          TEXT    NOT NULL,
            hectareas     REAL    NOT NULL CHECK (hectareas > 0),
            lote          TEXT    NOT NULL DEFAULT '',
            cultivo       TEXT    NOT NULL DEFAULT '',
            observaciones TEXT    NOT NULL DEFAULT '',
            creado_en     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE vencimientos (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion       TEXT    NOT NULL,
            tipo              TEXT    NOT NULL,
            fecha_vencimiento TEXT    NOT NULL,
            maquina_id        INTEGER REFERENCES maquinas(id),
            resuelto          INTEGER NOT NULL DEFAULT 0 CHECK (resuelto IN (0, 1)),
            observaciones     TEXT    NOT NULL DEFAULT '',
            creado_en         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE contactos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT    NOT NULL,
            rubro     TEXT    NOT NULL,
            empresa   TEXT    NOT NULL DEFAULT '',
            telefono  TEXT    NOT NULL DEFAULT '',
            email     TEXT    NOT NULL DEFAULT '',
            notas     TEXT    NOT NULL DEFAULT '',
            creado_en TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        "CREATE INDEX idx_mantenimientos_maquina ON mantenimientos(maquina_id)",
        "CREATE INDEX idx_trabajos_maquina ON trabajos(maquina_id)",
    ],
    # 2) Insumos: subcategoría, archivado, máquina (para repuestos) y stock mínimo
    [
        "ALTER TABLE insumos ADD COLUMN subcategoria TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE insumos ADD COLUMN archivado INTEGER NOT NULL DEFAULT 0 CHECK (archivado IN (0, 1))",
        "ALTER TABLE insumos ADD COLUMN maquina_id INTEGER REFERENCES maquinas(id)",
        "ALTER TABLE insumos ADD COLUMN stock_minimo REAL NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0)",
        "CREATE INDEX idx_movimientos_insumo ON movimientos(insumo_id)",
    ],
    # 3) Ganadería
    [
        """
        CREATE TABLE animales (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            caravana             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            categoria            TEXT    NOT NULL,
            raza                 TEXT    NOT NULL DEFAULT '',
            rodeo                TEXT    NOT NULL DEFAULT '',
            fecha_nacimiento     TEXT,
            estado_reproductivo  TEXT    NOT NULL DEFAULT ''
                                 CHECK (estado_reproductivo IN ('', 'vacia', 'prenada')),
            fecha_probable_parto TEXT,
            madre_id             INTEGER REFERENCES animales(id),
            estado               TEXT    NOT NULL DEFAULT 'activo'
                                 CHECK (estado IN ('activo', 'vendido', 'muerto')),
            observaciones        TEXT    NOT NULL DEFAULT '',
            creado_en            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE eventos_animales (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_id     INTEGER NOT NULL REFERENCES animales(id),
            fecha         TEXT    NOT NULL,
            tipo          TEXT    NOT NULL,
            resultado     TEXT    NOT NULL DEFAULT '',
            crias_machos  INTEGER NOT NULL DEFAULT 0 CHECK (crias_machos >= 0),
            crias_hembras INTEGER NOT NULL DEFAULT 0 CHECK (crias_hembras >= 0),
            detalle       TEXT    NOT NULL DEFAULT '',
            creado_en     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        "CREATE INDEX idx_eventos_animal ON eventos_animales(animal_id)",
    ],
    # 4) Service programado por horas (varios planes por máquina)
    [
        """
        CREATE TABLE planes_service (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            maquina_id   INTEGER NOT NULL REFERENCES maquinas(id),
            nombre       TEXT    NOT NULL,
            cada_horas   REAL    NOT NULL CHECK (cada_horas > 0),
            medida       TEXT    NOT NULL DEFAULT 'motor' CHECK (medida IN ('motor', 'trilla')),
            ultima_horas REAL    NOT NULL DEFAULT 0 CHECK (ultima_horas >= 0),
            ultima_fecha TEXT,
            activo       INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
            creado_en    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        "CREATE UNIQUE INDEX idx_planes_nombre ON planes_service(maquina_id, nombre COLLATE NOCASE)",
    ],
]


def version_actual():
    with conectar() as conexion:
        return conexion.execute("PRAGMA user_version").fetchone()[0]


def migraciones_pendientes():
    """Cuántas migraciones faltan aplicar (0 si la base está al día)."""
    if not DB_PATH.exists():
        return 0  # Base nueva: no hay datos que proteger con un backup.
    return len(MIGRACIONES) - version_actual()


def migrar():
    """Aplica las migraciones que faltan. Cada una va en su propia transacción."""
    with conectar() as conexion:
        version = conexion.execute("PRAGMA user_version").fetchone()[0]

    for numero in range(version + 1, len(MIGRACIONES) + 1):
        with conectar() as conexion:
            # BEGIN explícito: así hasta los CREATE/ALTER quedan dentro de la
            # transacción. Si algo falla, no se aplica NADA de esta migración.
            if not conexion.in_transaction:
                conexion.execute("BEGIN")
            for sentencia in MIGRACIONES[numero - 1]:
                conexion.execute(sentencia)
            conexion.execute(f"PRAGMA user_version = {numero}")
        print(f"Base de datos actualizada a la versión {numero}.")


def crear_tablas():
    """Crea las tablas base si no existen y aplica las migraciones pendientes.

    Se puede llamar muchas veces sin perder datos.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # Crea datos/ si no existe.
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
    migrar()
