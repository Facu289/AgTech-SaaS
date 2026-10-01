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
    monkeypatch.setattr(database, "MIGRACIONES", todas[:5])
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()

    from app.insumos import db as insumos_db
    importlib.reload(insumos_db)
    por_nombre = {i["nombre"]: i["maquinas"] for i in insumos_db.listar_insumos()}
    assert por_nombre == {"Filtro": [{"id": 1, "nombre": "JD"}], "Grasa": []}


def test_migracion_6_agrega_serie_del_monitor_sin_tocar_las_maquinas(tmp_path, monkeypatch):
    """Las máquinas que ya existían quedan iguales, con el N° de serie del monitor vacío."""
    import importlib

    from app.nucleo import database
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "v5.db"))
    importlib.reload(database)
    todas = database.MIGRACIONES
    monkeypatch.setattr(database, "MIGRACIONES", todas[:5])
    database.crear_tablas()
    with database.conectar() as conexion:
        conexion.execute("INSERT INTO maquinas (nombre, tipo, numero_serie) VALUES ('Sembradora', 'sembradora', 'ABC1')")
    monkeypatch.setattr(database, "MIGRACIONES", todas[:6])
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()
    with database.conectar() as conexion:
        fila = conexion.execute("SELECT nombre, numero_serie, serie_monitor FROM maquinas").fetchone()
    assert tuple(fila) == ("Sembradora", "ABC1", "")


def test_migracion_7_pasa_los_animales_a_vacuno_sin_perder_nada(tmp_path, monkeypatch):
    """Los animales de antes quedan como Vacuno, con su categoría, su madre y sus eventos."""
    import importlib
    import sqlite3

    from app.nucleo import database
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "v6.db"))
    importlib.reload(database)
    todas = database.MIGRACIONES
    # 1) Base en la versión 6, con una vaca, su cría y un evento.
    monkeypatch.setattr(database, "MIGRACIONES", todas[:6])
    database.crear_tablas()
    with database.conectar() as conexion:
        conexion.execute("INSERT INTO animales (caravana, categoria, estado_reproductivo) VALUES ('100', 'vaca', 'vacia')")
        conexion.execute("INSERT INTO animales (caravana, categoria, madre_id) VALUES ('100-A', 'ternera', 1)")
        conexion.execute("INSERT INTO eventos_animales (animal_id, fecha, tipo, crias_hembras) VALUES (1, '2026-09-01', 'parto', 1)")
    # 2) Se aplica la migración 7.
    monkeypatch.setattr(database, "MIGRACIONES", todas[:7])
    assert database.migraciones_pendientes() == 1
    database.crear_tablas()

    from app.ganaderia import db as ganaderia_db
    importlib.reload(ganaderia_db)
    animales = {a["caravana"]: a for a in ganaderia_db.listar_animales()}
    assert (animales["100"]["especie"], animales["100"]["categoria"], animales["100"]["partos"]) == ("Vacuno", "Vaca", 1)
    assert animales["100"]["estado_reproductivo"] == "vacia"
    assert (animales["100-A"]["categoria"], animales["100-A"]["madre_caravana"]) == ("Ternera", "100")
    conexion = sqlite3.connect(database.DB_PATH)
    assert conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conexion.execute("PRAGMA foreign_key_check").fetchall() == []
    # Ahora la caravana se puede repetir (la base ya no lo impide; la app pide confirmación).
    conexion.execute("INSERT INTO animales (caravana, categoria_id) VALUES ('100', 1)")
    conexion.close()
