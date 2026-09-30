"""Conexión a SQLite, migraciones y SQL de insumos, movimientos y notas.

Este archivo NO sabe nada de HTTP ni de Telegram: si algo no se puede hacer,
lanza una excepción (InsumoNoEncontrado, StockInsuficiente, ...) y quien lo
llamó decide qué mostrar.
El SQL de maquinaria y ganadería está en db_maquinaria.py y db_ganaderia.py.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# El archivo de la base se crea en la misma carpeta que este archivo.
# (Los tests usan otra base poniendo la variable de entorno AGROAPP_DB).
DB_PATH = Path(os.getenv("AGROAPP_DB", Path(__file__).parent / "agroapp.db"))


# ---------- Errores ----------

class NoEncontrado(Exception):
    """Se pidió algo (insumo, máquina, animal...) que no existe."""


class InsumoNoEncontrado(NoEncontrado):
    """Se pidió un insumo que no existe."""


class StockInsuficiente(Exception):
    """Se intentó sacar más de lo que hay."""

    def __init__(self, disponible):
        super().__init__(f"Stock insuficiente: hay {disponible}")
        self.disponible = disponible


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


# ---------- Insumos ----------

# La misma consulta sirve para listar y para buscar uno (así devuelven lo mismo).
SELECT_INSUMOS = """
    SELECT i.id, i.nombre, i.categoria, i.subcategoria, i.unidad, i.cantidad,
           i.stock_minimo, i.maquina_id, m.nombre AS maquina_nombre, i.archivado,
           EXISTS (SELECT 1 FROM movimientos mv WHERE mv.insumo_id = i.id) AS tiene_movimientos
    FROM insumos i
    LEFT JOIN maquinas m ON m.id = i.maquina_id
"""


def _obtener_insumo(conexion, insumo_id):
    """Busca un insumo por id usando una conexión ya abierta. Devuelve dict o None."""
    fila = conexion.execute(SELECT_INSUMOS + " WHERE i.id = ?", (insumo_id,)).fetchone()
    return dict(fila) if fila else None


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
        return filas_a_dicts(filas)


def agregar_insumo(nombre, categoria, unidad, cantidad=0, subcategoria="", maquina_id=None, stock_minimo=0):
    """Guarda un insumo nuevo (y su stock inicial) y lo devuelve como diccionario."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "INSERT INTO insumos (nombre, categoria, subcategoria, unidad, cantidad, maquina_id, stock_minimo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre, categoria, subcategoria, unidad, cantidad, maquina_id, stock_minimo),
        )
        insumo_id = cursor.lastrowid
        if cantidad > 0:
            conexion.execute(
                "INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo) "
                "VALUES (?, 'entrada', ?, 'stock inicial')",
                (insumo_id, cantidad),
            )
        return _obtener_insumo(conexion, insumo_id)


def editar_insumo(insumo_id, nombre, categoria, subcategoria, unidad, maquina_id, stock_minimo):
    """Cambia los datos de un insumo (NO la cantidad: eso se hace con movimientos)."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE insumos SET nombre = ?, categoria = ?, subcategoria = ?, unidad = ?, "
            "maquina_id = ?, stock_minimo = ? WHERE id = ?",
            (nombre, categoria, subcategoria, unidad, maquina_id, stock_minimo, insumo_id),
        )
        if cursor.rowcount == 0:
            raise InsumoNoEncontrado()
        return _obtener_insumo(conexion, insumo_id)


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
        return filas_a_dicts(filas)


def marcar_nota_hecha(nota_id):
    """Marca una nota como hecha. Devuelve True si existía y estaba pendiente."""
    with conectar() as conexion:
        cursor = conexion.execute(
            "UPDATE notas SET hecha = 1 WHERE id = ? AND hecha = 0", (nota_id,)
        )
        return cursor.rowcount == 1
