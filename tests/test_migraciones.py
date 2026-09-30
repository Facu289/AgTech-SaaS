"""La migración NO puede perder datos de una base vieja (la que ya tenés cargada)."""
import sqlite3


def test_base_vieja_se_migra_sin_perder_datos(tmp_path, monkeypatch):
    ruta = tmp_path / "vieja.db"
    # Armamos una base con la estructura de ANTES de las migraciones.
    conexion = sqlite3.connect(ruta)
    conexion.executescript("""
        CREATE TABLE insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            categoria TEXT NOT NULL, unidad TEXT NOT NULL, cantidad REAL NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, insumo_id INTEGER NOT NULL REFERENCES insumos(id),
            tipo TEXT NOT NULL, cantidad REAL NOT NULL, motivo TEXT NOT NULL DEFAULT '',
            fecha TEXT NOT NULL DEFAULT (datetime('now', 'localtime')));
        INSERT INTO insumos (nombre, categoria, unidad, cantidad) VALUES ('glifosato', 'agroquimico', 'litros', 10);
        INSERT INTO movimientos (insumo_id, tipo, cantidad, motivo) VALUES (1, 'entrada', 10, 'stock inicial');
    """)
    conexion.close()

    monkeypatch.setenv("AGROAPP_DB", str(ruta))
    import importlib
    import database
    importlib.reload(database)
    assert database.migraciones_pendientes() == len(database.MIGRACIONES)

    database.crear_tablas()
    database.crear_tablas()  # Dos veces: no tiene que fallar ni duplicar nada.

    assert database.migraciones_pendientes() == 0
    insumo = database.listar_insumos()[0]
    assert (insumo["nombre"], insumo["cantidad"], insumo["subcategoria"]) == ("glifosato", 10, "")
    assert len(database.listar_movimientos(1)) == 1
