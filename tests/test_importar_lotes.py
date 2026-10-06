"""Tests de importar lotes (KMZ, KML, GeoJSON) y exportarlos a KML."""
import base64
import io
import json
import zipfile

import pytest

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Campo</name>
    <Folder>
      <Placemark>
        <name>La Loma</name>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>
          -63.90,-31.63,0 -63.888,-31.63,0 -63.888,-31.62,0 -63.90,-31.62,0 -63.90,-31.63,0
        </coordinates></LinearRing></outerBoundaryIs></Polygon>
      </Placemark>
      <Placemark>
        <name>El Bajo</name>
        <MultiGeometry>
          <Polygon><outerBoundaryIs><LinearRing><coordinates>
            -63.80,-31.63 -63.79,-31.63 -63.79,-31.62 -63.80,-31.63
          </coordinates></LinearRing></outerBoundaryIs></Polygon>
          <Polygon><outerBoundaryIs><LinearRing><coordinates>
            -63.70,-31.63 -63.69,-31.63 -63.69,-31.62 -63.70,-31.63
          </coordinates></LinearRing></outerBoundaryIs></Polygon>
        </MultiGeometry>
      </Placemark>
      <Placemark>
        <name>Molino</name>
        <Point><coordinates>-63.85,-31.625,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Borde como línea</name>
        <LineString><coordinates>
          -63.60,-31.63 -63.59,-31.63 -63.59,-31.62 -63.60,-31.62 -63.60,-31.63
        </coordinates></LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""


def kmz(texto_kml=KML):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as archivo:
        archivo.writestr("doc.kml", texto_kml)
    return memoria.getvalue()


def leer(cliente, nombre, contenido: bytes):
    return cliente.post("/lotes/importar/leer", json={
        "nombre_archivo": nombre, "contenido_base64": base64.b64encode(contenido).decode(),
    })


# ---------- Leer archivos (sin guardar) ----------

def test_leer_kml(app):
    from app.lotes import importar
    lotes, errores = importar.leer_archivo("campo.kml", KML.encode())
    nombres = [l["nombre"] for l in lotes]
    # El punto (Molino) no es un lote; el MultiGeometry da dos; la línea cerrada se toma como borde.
    assert nombres == ["La Loma", "El Bajo (1)", "El Bajo (2)", "Borde como línea"]
    assert lotes[0]["hectareas"] == pytest.approx(126.24, rel=0.002)
    assert errores == []


def test_leer_kmz_da_lo_mismo_que_el_kml(app):
    from app.lotes import importar
    assert importar.leer_archivo("campo.kmz", kmz())[0] == importar.leer_archivo("campo.kml", KML.encode())[0]


def test_leer_geojson_con_nombre_en_propiedades(app):
    from app.lotes import importar
    datos = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"NAME": "Potrero 1"}, "geometry": {
            "type": "Polygon", "coordinates": [[[-63.9, -31.63], [-63.89, -31.63], [-63.89, -31.62], [-63.9, -31.63]]]}},
        {"type": "Feature", "properties": {}, "geometry": {
            "type": "Polygon", "coordinates": [[[-63.8, -31.63], [-63.79, -31.63], [-63.79, -31.62], [-63.8, -31.63]]]}},
    ]}
    lotes, _ = importar.leer_archivo("lotes.geojson", json.dumps(datos).encode())
    assert [l["nombre"] for l in lotes] == ["Potrero 1", "Lote 2"]


def test_nombres_repetidos_en_el_archivo(app):
    from app.lotes import importar
    repetido = KML.replace("El Bajo", "La Loma").replace("Borde como línea", "La Loma")
    nombres = [l["nombre"] for l in importar.leer_archivo("x.kml", repetido.encode())[0]]
    assert len(nombres) == len(set(n.lower() for n in nombres))


def test_coordenadas_que_no_son_grados_dan_error_por_lote(app):
    """Ej: un archivo en UTM (metros): no se puede ubicar en el mapa."""
    from app.lotes import importar
    utm = KML.replace("-63.90,-31.63", "450000,6500000")
    lotes, errores = importar.leer_archivo("utm.kml", utm.encode())
    assert "La Loma" not in [l["nombre"] for l in lotes]
    assert errores and "La Loma" in errores[0]


@pytest.mark.parametrize("nombre, contenido", [
    ("lotes.kmz", b"PK\x03\x04 esto no es un zip"),
    ("lotes.kml", b"<kml><Placemark>sin cerrar"),
    ("lotes.txt", b"hola"),
    ("puntos.kml", KML.split("<Folder>")[0].encode() + b"</Document></kml>"),
])
def test_archivos_invalidos(app, nombre, contenido):
    from app.lotes import importar
    with pytest.raises(importar.ArchivoInvalido):
        importar.leer_archivo(nombre, contenido)


# ---------- Endpoints ----------

def test_vista_previa_marca_los_que_ya_existen(cliente):
    cliente.post("/lotes", json={"nombre": "la loma"})
    r = leer(cliente, "campo.kmz", kmz())
    assert r.status_code == 200, r.text
    previa = {l["nombre"]: l for l in r.json()["lotes"]}
    assert previa["La Loma"]["existente"]["nombre"] == "la loma"
    assert previa["El Bajo (1)"]["existente"] is None
    assert cliente.get("/lotes").json()[0]["geometria"] is None  # Leer NO guarda nada.


def test_archivo_invalido_responde_400(cliente):
    assert leer(cliente, "x.txt", b"hola").status_code == 400
    r = cliente.post("/lotes/importar/leer", json={"nombre_archivo": "x.kmz", "contenido_base64": "no es base64!"})
    assert r.status_code == 400


def test_importar_crea_actualiza_y_saltea(cliente):
    cliente.post("/lotes", json={"nombre": "La Loma", "hectareas": "100"})  # Ya existe, ha a mano.
    cliente.post("/lotes", json={"nombre": "El Bajo (1)", "observaciones": "no tocar"})
    previa = {l["nombre"]: l for l in leer(cliente, "campo.kmz", kmz()).json()["lotes"]}
    r = cliente.post("/lotes/importar", json={"lotes": [
        {"nombre": "La Loma", "geometria": previa["La Loma"]["geometria"], "actualizar": True},
        {"nombre": "El Bajo (1)", "geometria": previa["El Bajo (1)"]["geometria"]},
        {"nombre": "El Bajo (2)", "geometria": previa["El Bajo (2)"]["geometria"]},
        {"nombre": "Malo", "geometria": {"type": "Point", "coordinates": [0, 0]}},
    ]})
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["creados"] == ["El Bajo (2)"]
    assert resultado["actualizados"] == ["La Loma"]
    assert resultado["salteados"] == ["El Bajo (1)"]
    assert len(resultado["errores"]) == 1 and "Malo" in resultado["errores"][0]

    lotes = {l["nombre"]: l for l in cliente.get("/lotes").json()}
    assert lotes["La Loma"]["geometria"] is not None
    assert lotes["La Loma"]["hectareas"] == 100  # Las ha a mano se respetan al cambiar la forma.
    assert lotes["El Bajo (1)"]["geometria"] is None


def test_exportar_kml_y_volver_a_importar(cliente):
    from test_lotes import crear_campania, cuadrado, sembrar

    lote = cliente.post("/lotes", json={"nombre": "Lote <4> & Cía", "geometria": cuadrado()}).json()
    campania = crear_campania(cliente)
    sembrar(cliente, lote, campania, "Soja")
    r = cliente.get(f"/exportar/lotes-kml?campania_id={campania['id']}")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    texto = r.content.decode()
    assert "Soja" in texto and "&lt;4&gt; &amp; Cía" in texto  # Nombre raro bien escapado.
    assert "ff4aa316" in texto  # Color de la soja (#16A34A) en formato KML (al revés).

    # Ida y vuelta: lo exportado se vuelve a leer igual.
    previa = leer(cliente, "lotes.kml", r.content).json()["lotes"]
    assert previa[0]["nombre"] == "Lote <4> & Cía"
    assert previa[0]["hectareas"] == lote["hectareas"]


def test_importar_pide_login(cliente_anonimo):
    assert cliente_anonimo.post("/lotes/importar", json={"lotes": []}).status_code == 401
    assert cliente_anonimo.get("/exportar/lotes-kml").status_code == 401
