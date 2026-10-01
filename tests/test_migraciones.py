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



def test_migracion_5_copia_la_maquina_que_ya_tenia_cada_repuesto(tmp_path, monkeypatch):
    """Los repuestos que ya tenían UNA máquina (columna vieja) la conservan en la tabla nueva."""
    import importlib

    from app.nucleo import database
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "v4.db"))
    importlib.reload(database)
    todas = database.MIGRACIONES
    # 1) Base en la versión 4 (como estaba antes de este cambio), con un repuesto asignado.
    monkeypatch.setattr(database, "MIGRACIONES", todas[:4])
    database.crear_tablas()
    with database.conectar() as conexion:
        conexion.execute("INSERT INTO maquinas (nombre, tipo) VALUES ('JD', 'tractor')")
        conexion.execute("INSERT INTO insumos (nombre, categoria, unidad, maquina_id) VALUES ('Filtro', 'repuesto', 'unidades', 1)")
        conexion.execute("INSERT INTO insumos (nombre, categoria, unidad) VALUES ('Grasa', 'repuesto', 'kg')")
    # 2) Se aplica la migración 5.
    monkeypatch.setattr(database, "MIGRACIONES", todas)
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()

    from app.insumos import db as insumos_db
    importlib.reload(insumos_db)
    por_nombre = {i["nombre"]: i["maquinas"] for i in insumos_db.listar_insumos()}
    assert por_nombre == {"Filtro": [{"id": 1, "nombre": "JD"}], "Grasa": []}
