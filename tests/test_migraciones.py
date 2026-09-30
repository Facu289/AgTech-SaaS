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
    from app.nucleo import database
    importlib.reload(database)
    assert database.migraciones_pendientes() == len(database.MIGRACIONES)

    database.crear_tablas()
    database.crear_tablas()  # Dos veces: no tiene que fallar ni duplicar nada.

    assert database.migraciones_pendientes() == 0
    from app.insumos import db as insumos_db
    importlib.reload(insumos_db)
    insumo = insumos_db.listar_insumos()[0]
    assert (insumo["nombre"], insumo["cantidad"], insumo["subcategoria"]) == ("glifosato", 10, "")
    assert len(insumos_db.listar_movimientos(1)) == 1


def test_no_arranca_con_la_base_en_el_lugar_viejo(tmp_path, monkeypatch):
    """Si la base sigue en la raíz (sin reorganizar), NO se crea una base vacía en datos/."""
    import importlib

    import pytest

    from app.nucleo import database
    monkeypatch.delenv("AGROAPP_DB", raising=False)
    importlib.reload(database)
    monkeypatch.setattr(database, "CARPETA_PROYECTO", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "datos" / "agroapp.db")
    (tmp_path / "agroapp.db").write_bytes(b"")  # La base "vieja", en la raíz.
    with pytest.raises(database.UbicacionVieja, match="reorganizar.ps1"):
        database.verificar_ubicacion()
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "agroapp.db").write_bytes(b"")  # Ya movida: todo bien.
    database.verificar_ubicacion()
