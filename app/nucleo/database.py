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
    # 5) Un repuesto puede servir para VARIAS máquinas.
    #    Tabla intermedia ("muchos a muchos"): una fila por cada par repuesto-máquina.
    #    Se copian las asignaciones que ya existían en insumos.maquina_id, y esa columna
    #    queda vacía y sin uso (SQLite no deja borrar columnas que son referencias).
    [
        """
        CREATE TABLE insumo_maquinas (
            insumo_id  INTEGER NOT NULL REFERENCES insumos(id),
            maquina_id INTEGER NOT NULL REFERENCES maquinas(id),
            PRIMARY KEY (insumo_id, maquina_id)
        )
        """,
        "CREATE INDEX idx_insumo_maquinas_maquina ON insumo_maquinas(maquina_id)",
        "INSERT INTO insumo_maquinas (insumo_id, maquina_id) SELECT id, maquina_id FROM insumos WHERE maquina_id IS NOT NULL",
        "UPDATE insumos SET maquina_id = NULL",
    ],
    # 6) N° de serie del monitor (GPS / piloto) de cada máquina.
    #    Se guarda en la máquina y no en cada licencia: se carga una vez y todas las
    #    licencias y suscripciones de esa máquina lo muestran.
    [
        "ALTER TABLE maquinas ADD COLUMN serie_monitor TEXT NOT NULL DEFAULT ''",
    ],
    # 7) Especies: vacunos, ovinos, porcinos, gallinas... las crea el usuario.
    #    - Cada especie tiene sus categorías, y cada categoría dice si es hembra o macho.
    #    - Los días de gestación son de la especie (vacas 283). Vacío = sin preñez (aves).
    #    - Un animal puede ser un GRUPO (ej: 120 gallinas ponedoras) con una cantidad.
    #    - La caravana ya no es única: se puede repetir entre animales (la app avisa antes).
    #    Para sacar el UNIQUE de la caravana hay que RECONSTRUIR la tabla animales
    #    (SQLite no deja borrar esa restricción): tabla nueva → copiar → borrar vieja → renombrar.
    #    Todos los animales que ya había pasan a la especie Vacuno, con su misma categoría.
    [
        """
        CREATE TABLE especies (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            dias_gestacion INTEGER CHECK (dias_gestacion IS NULL OR dias_gestacion > 0),
            creado_en      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        """
        CREATE TABLE categorias_animal (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            especie_id INTEGER NOT NULL REFERENCES especies(id),
            nombre     TEXT    NOT NULL,
            sexo       TEXT    NOT NULL DEFAULT '' CHECK (sexo IN ('hembra', 'macho', '')),
            creado_en  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """,
        "CREATE UNIQUE INDEX idx_categorias_nombre ON categorias_animal(especie_id, nombre COLLATE NOCASE)",
        "INSERT INTO especies (id, nombre, dias_gestacion) VALUES (1, 'Vacuno', 283)",
        """
        INSERT INTO categorias_animal (especie_id, nombre, sexo) VALUES
            (1, 'Vaca', 'hembra'), (1, 'Vaquillona', 'hembra'), (1, 'Ternera', 'hembra'),
            (1, 'Ternero', 'macho'), (1, 'Novillo', 'macho'), (1, 'Toro', 'macho')
        """,
        # Por las dudas: si algún animal tenía otra categoría, se crea (sin sexo) para no perderlo.
        """
        INSERT INTO categorias_animal (especie_id, nombre)
        SELECT 1, MIN(categoria) FROM animales
        WHERE lower(categoria) NOT IN (SELECT lower(nombre) FROM categorias_animal)
        GROUP BY lower(categoria)
        """,
        """
        CREATE TABLE animales_nueva (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            caravana             TEXT    NOT NULL COLLATE NOCASE,
            categoria_id         INTEGER NOT NULL REFERENCES categorias_animal(id),
            es_grupo             INTEGER NOT NULL DEFAULT 0 CHECK (es_grupo IN (0, 1)),
            cantidad             INTEGER NOT NULL DEFAULT 1 CHECK (cantidad >= 0),
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
        INSERT INTO animales_nueva (id, caravana, categoria_id, raza, rodeo, fecha_nacimiento,
            estado_reproductivo, fecha_probable_parto, madre_id, estado, observaciones, creado_en)
        SELECT a.id, a.caravana, c.id, a.raza, a.rodeo, a.fecha_nacimiento,
            a.estado_reproductivo, a.fecha_probable_parto, a.madre_id, a.estado, a.observaciones, a.creado_en
        FROM animales a
        JOIN categorias_animal c ON c.especie_id = 1 AND lower(c.nombre) = lower(a.categoria)
        """,
        "DROP TABLE animales",
        "ALTER TABLE animales_nueva RENAME TO animales",
        "CREATE INDEX idx_animales_caravana ON animales(caravana)",
        "CREATE INDEX idx_animales_categoria ON animales(categoria_id)",
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
            # Durante la migración se apagan las relaciones (foreign keys): si no,
            # reconstruir una tabla (borrar la vieja) fallaría. Se apaga ANTES del
            # BEGIN porque SQLite no deja cambiarlo dentro de una transacción.
            conexion.execute("PRAGMA foreign_keys = OFF")
            # BEGIN explícito: así hasta los CREATE/ALTER quedan dentro de la
            # transacción. Si algo falla, no se aplica NADA de esta migración.
            if not conexion.in_transaction:
                conexion.execute("BEGIN")
            for sentencia in MIGRACIONES[numero - 1]:
                conexion.execute(sentencia)
            # Antes de guardar, revisamos que ninguna relación haya quedado rota.
            rotas = conexion.execute("PRAGMA foreign_key_check").fetchall()
            if rotas:
                raise RuntimeError(f"La migración {numero} dejó {len(rotas)} relaciones rotas: no se aplicó.")
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
