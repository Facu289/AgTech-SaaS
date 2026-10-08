"""Campo (establecimiento) de los lotes: el nombre es único por campo, no en toda la app."""
import base64
import sqlite3

from test_importar_lotes import KML, kmz
from test_lotes import cuadrado


def test_mismo_nombre_en_campos_distintos(cliente):
    for campo in ("LM", "SR Oeste"):
        r = cliente.post("/lotes", json={"campo": campo, "nombre": "1", "geometria": cuadrado()})
        assert r.status_code == 201, r.text
    r = cliente.post("/lotes", json={"campo": "lm", "nombre": "1"})  # Mismo campo (sin importar mayúsculas).
    assert r.status_code == 409 and "LM" in r.json()["detail"]
    assert [(l["campo"], l["nombre"]) for l in cliente.get("/lotes").json()] == [("LM", "1"), ("SR Oeste", "1")]


def test_mover_un_lote_de_campo(cliente):
    lote = cliente.post("/lotes", json={"campo": "LM", "nombre": "5"}).json()
    cliente.post("/lotes", json={"campo": "SR Oeste", "nombre": "5"})
    # Pasarlo a SR Oeste choca con el "5" que ya está ahí.
    assert cliente.put(f"/lotes/{lote['id']}", json={"campo": "SR Oeste", "nombre": "5"}).status_code == 409
    assert cliente.put(f"/lotes/{lote['id']}", json={"campo": "Norte", "nombre": "5"}).json()["campo"] == "Norte"


def test_importar_usa_la_carpeta_como_campo(cliente):
    con_carpeta = KML.replace("<Folder>", "<Folder><name>Santa Rita Oeste</name>", 1)
    r = cliente.post("/lotes/importar/leer", json={
        "nombre_archivo": "campo.kmz", "contenido_base64": base64.b64encode(kmz(con_carpeta)).decode(),
    })
    previa = r.json()["lotes"]
    assert {l["campo"] for l in previa} == {"Santa Rita Oeste"}
    # Se guarda con el campo que se elija en la vista previa.
    r = cliente.post("/lotes/importar", json={"lotes": [
        {"campo": "SR Oeste", "nombre": previa[0]["nombre"], "geometria": previa[0]["geometria"]},
    ]})
    assert r.json()["creados"] == ["La Loma"]
    assert cliente.get("/lotes").json()[0]["campo"] == "SR Oeste"


def test_importar_mismo_nombre_en_otro_campo_crea_uno_nuevo(cliente):
    cliente.post("/lotes", json={"campo": "LM", "nombre": "La Loma"})
    r = cliente.post("/lotes/importar", json={"lotes": [
        {"campo": "SR Oeste", "nombre": "La Loma", "geometria": cuadrado(), "actualizar": True},
    ]})
    assert r.json()["creados"] == ["La Loma"] and r.json()["actualizados"] == []


def test_kml_exportado_trae_carpeta_por_campo(cliente):
    cliente.post("/lotes", json={"campo": "LM", "nombre": "31", "geometria": cuadrado()})
    cliente.post("/lotes", json={"campo": "SR Oeste", "nombre": "1", "geometria": cuadrado(latitud=-31)})
    kml = cliente.get("/exportar/lotes-kml").content
    texto = kml.decode()
    assert texto.count("<Folder>") == 2 and "<name>SR Oeste</name>" in texto
    # Ida y vuelta: al importar lo exportado, cada lote vuelve con su campo.
    r = cliente.post("/lotes/importar/leer", json={
        "nombre_archivo": "lotes.kml", "contenido_base64": base64.b64encode(kml).decode(),
    })
    assert sorted((l["campo"], l["nombre"]) for l in r.json()["lotes"]) == [("LM", "31"), ("SR Oeste", "1")]
    assert all(l["existente"] for l in r.json()["lotes"])


def test_migracion_12_conserva_los_lotes_y_sus_cultivos(tmp_path, monkeypatch):
    """Una base en versión 11 (con lotes y cultivos) pasa a la 12 sin perder nada."""
    import importlib

    from app.nucleo import database

    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "vieja.db"))
    importlib.reload(database)
    database.crear_tablas()  # Base nueva hasta la última versión...
    with database.conectar() as conexion:
        conexion.execute("PRAGMA foreign_keys = OFF")
        # ...y la "volvemos" a la versión 11: la tabla lotes como era antes (nombre único, sin campo).
        conexion.execute("DROP TABLE lotes")
        conexion.execute(
            "CREATE TABLE lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE, "
            "geometria TEXT, hectareas REAL, observaciones TEXT NOT NULL DEFAULT '', archivado INTEGER NOT NULL DEFAULT 0, "
            "creado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime')), "
            "actualizado_en TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
        )
        conexion.execute("INSERT INTO lotes (id, nombre, hectareas) VALUES (7, 'La Loma', 120.5)")
        conexion.execute("INSERT INTO campanias (id, nombre) VALUES (1, '2026/27')")
        conexion.execute("INSERT INTO lote_cultivos (lote_id, campania_id, cultivo_id) VALUES (7, 1, 1)")
        conexion.execute("PRAGMA user_version = 11")

    database.migrar()

    conexion = sqlite3.connect(tmp_path / "vieja.db")
    assert conexion.execute("PRAGMA user_version").fetchone()[0] == len(database.MIGRACIONES)
    assert conexion.execute("SELECT id, campo, nombre, hectareas FROM lotes").fetchall() == [(7, "", "La Loma", 120.5)]
    assert conexion.execute("SELECT lote_id FROM lote_cultivos").fetchall() == [(7,)]
    assert conexion.execute("PRAGMA foreign_key_check").fetchall() == []
    conexion.close()
