"""Tests de lotes: el polígono, las hectáreas y los endpoints."""
import sqlite3

import pytest


def cuadrado(latitud=-30.0, longitud=-63.0, lado=0.01, cerrado=True):
    """Un cuadrado de 'lado' grados (0,01° ≈ 1 km) con la esquina en (longitud, latitud)."""
    puntos = [
        [longitud, latitud], [longitud + lado, latitud], [longitud + lado, latitud + lado],
        [longitud, latitud + lado],
    ]
    if cerrado:
        puntos.append([longitud, latitud])
    return {"type": "Polygon", "coordinates": [puntos]}


def crear_lote(cliente, **datos):
    base = {"nombre": "La Loma", "geometria": cuadrado()}
    r = cliente.post("/lotes", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- Cálculo de hectáreas ----------

def test_hectareas_contra_tablas_del_elipsoide(app):
    """A 30° de latitud, 0,01° de latitud = 1.108,52 m y 0,01° de longitud = 964,86 m
    (tablas del elipsoide WGS84). El cuadrado de 0,01° mide entonces 106,96 ha."""
    from app.lotes import geometria
    ha = geometria.hectareas(geometria.validar_poligono(cuadrado(latitud=-30.005)))
    assert ha == pytest.approx(106.96, rel=0.001)


def test_el_sentido_del_dibujo_no_cambia_el_area(app):
    from app.lotes import geometria
    poligono = cuadrado()
    al_reves = {"type": "Polygon", "coordinates": [list(reversed(poligono["coordinates"][0]))]}
    assert geometria.hectareas(poligono) == geometria.hectareas(al_reves)


def test_un_hueco_resta_superficie(app):
    from app.lotes import geometria
    borde = cuadrado(lado=0.02)["coordinates"][0]
    hueco = cuadrado(latitud=-29.995, longitud=-62.995)["coordinates"][0]  # 0,01° adentro del borde.
    con_hueco = geometria.validar_poligono({"type": "Polygon", "coordinates": [borde, hueco]})
    sin_hueco = geometria.validar_poligono({"type": "Polygon", "coordinates": [borde]})
    assert geometria.hectareas(con_hueco) == pytest.approx(
        geometria.hectareas(sin_hueco) * 3 / 4, rel=0.001
    )


# ---------- Migración ----------

def test_migracion_crea_la_tabla_lotes(app):
    from app.nucleo import database
    with database.conectar() as conexion:
        columnas = {fila["name"] for fila in conexion.execute("PRAGMA table_info(lotes)")}
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
    assert version == len(database.MIGRACIONES) >= 10
    assert {"id", "nombre", "geometria", "hectareas", "observaciones", "archivado",
            "creado_en", "actualizado_en"} <= columnas


def test_la_base_no_acepta_hectareas_negativas(app):
    from app.nucleo import database
    with pytest.raises(sqlite3.IntegrityError):
        with database.conectar() as conexion:
            conexion.execute("INSERT INTO lotes (nombre, hectareas) VALUES ('x', -1)")


# ---------- Endpoints ----------

def test_crear_lote_calcula_las_hectareas(cliente):
    lote = crear_lote(cliente, observaciones="Loma arenosa")
    assert lote["hectareas"] == lote["hectareas_calculadas"]
    assert lote["hectareas"] == pytest.approx(107, rel=0.01)
    assert lote["geometria"]["type"] == "Polygon"
    assert lote["archivado"] == 0
    assert [l["nombre"] for l in cliente.get("/lotes").json()] == ["La Loma"]


def test_hectareas_a_mano_se_respetan(cliente):
    lote = crear_lote(cliente, hectareas="98,5")  # Formato argentino, como en el resto de la app.
    assert lote["hectareas"] == 98.5
    assert lote["hectareas_calculadas"] == pytest.approx(107, rel=0.01)


def test_lote_sin_dibujo(cliente):
    lote = crear_lote(cliente, geometria=None, hectareas="")
    assert lote["geometria"] is None and lote["hectareas"] is None and lote["hectareas_calculadas"] is None


def test_poligono_abierto_se_cierra(cliente):
    lote = crear_lote(cliente, geometria=cuadrado(cerrado=False))
    anillo = lote["geometria"]["coordinates"][0]
    assert anillo[0] == anillo[-1] and len(anillo) == 5


@pytest.mark.parametrize("geometria", [
    {"type": "Point", "coordinates": [-63, -30]},
    {"type": "Polygon", "coordinates": []},
    {"type": "Polygon", "coordinates": [[[-63, -30], [-63.01, -30]]]},                          # 2 puntos
    {"type": "Polygon", "coordinates": [[[-63, -30], [-63.01, -30], [-63.02, -30]]]},           # en línea
    {"type": "Polygon", "coordinates": [[[-63, 100], [-63.01, -30], [-63.01, -30.01]]]},        # latitud 100
    {"type": "Polygon", "coordinates": [[["a", -30], [-63.01, -30], [-63.01, -30.01]]]},        # texto
])
def test_poligono_invalido(cliente, geometria):
    r = cliente.post("/lotes", json={"nombre": "Malo", "geometria": geometria})
    assert r.status_code == 422, r.text
    assert cliente.get("/lotes").json() == []


def test_nombre_repetido(cliente):
    crear_lote(cliente)
    r = cliente.post("/lotes", json={"nombre": "la lóma", "geometria": cuadrado()})
    assert r.status_code == 409
    assert "La Loma" in r.json()["detail"]


def test_editar_forma_recalcula_las_hectareas(cliente):
    lote = crear_lote(cliente)
    r = cliente.put(f"/lotes/{lote['id']}", json={
        "nombre": "La Loma", "geometria": cuadrado(lado=0.02), "hectareas": "", "observaciones": "",
    })
    assert r.status_code == 200, r.text
    assert r.json()["hectareas"] == pytest.approx(lote["hectareas"] * 4, rel=0.002)
    assert r.json()["actualizado_en"] >= lote["actualizado_en"]


def test_editar_con_el_mismo_nombre_no_choca_consigo_mismo(cliente):
    lote = crear_lote(cliente)
    r = cliente.put(f"/lotes/{lote['id']}", json={"nombre": "LA LOMA", "geometria": lote["geometria"]})
    assert r.status_code == 200 and r.json()["nombre"] == "LA LOMA"


def test_archivar_y_desarchivar(cliente):
    lote = crear_lote(cliente)
    assert cliente.post(f"/lotes/{lote['id']}/archivar").json()["archivado"] == 1
    assert cliente.get("/lotes").json() == []
    assert len(cliente.get("/lotes?incluir_archivados=true").json()) == 1
    # Archivado igual "ocupa" el nombre.
    assert cliente.post("/lotes", json={"nombre": "La Loma"}).status_code == 409
    assert cliente.post(f"/lotes/{lote['id']}/desarchivar").json()["archivado"] == 0


def test_eliminar(cliente):
    lote = crear_lote(cliente)
    assert cliente.delete(f"/lotes/{lote['id']}").status_code == 204
    assert cliente.get(f"/lotes/{lote['id']}").status_code == 404
    assert cliente.delete(f"/lotes/{lote['id']}").status_code == 404
    r = cliente.put(f"/lotes/{lote['id']}", json={"nombre": "Otro"})
    assert r.status_code == 404 and r.json()["detail"] == "No existe ese lote."


def test_lotes_piden_login(cliente_anonimo):
    assert cliente_anonimo.get("/lotes").status_code == 401
    assert cliente_anonimo.post("/lotes", json={"nombre": "X"}).status_code == 401
    r = cliente_anonimo.get("/web/lotes.html", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/web/login.html"


# ---------- Cultivos, campañas y cultivo de cada lote (migración 10) ----------

def crear_campania(cliente, nombre="2026/27"):
    r = cliente.post("/campanias", json={"nombre": nombre})
    assert r.status_code == 201, r.text
    return r.json()


def id_cultivo(cliente, nombre):
    return next(c["id"] for c in cliente.get("/cultivos").json() if c["nombre"] == nombre)


def sembrar(cliente, lote, campania, cultivo="Soja", **datos):
    cuerpo = {"campania_id": campania["id"], "cultivo_id": id_cultivo(cliente, cultivo), **datos}
    r = cliente.post(f"/lotes/{lote['id']}/cultivos", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_migracion_10_trae_cultivos_con_color(cliente):
    cultivos = {c["nombre"]: c for c in cliente.get("/cultivos").json()}
    assert {"Soja", "Maíz", "Trigo", "Girasol"} <= set(cultivos)
    assert cultivos["Soja"]["color"].startswith("#") and len(cultivos["Soja"]["color"]) == 7


def test_crear_editar_y_borrar_cultivo(cliente):
    r = cliente.post("/cultivos", json={"nombre": "Algodón", "color": "#ffffff"})
    assert r.status_code == 201 and r.json()["color"] == "#FFFFFF"
    nuevo = r.json()
    assert cliente.post("/cultivos", json={"nombre": "algodon", "color": "#000000"}).status_code == 409
    assert cliente.post("/cultivos", json={"nombre": "Maiz", "color": "#000000"}).status_code == 409  # "Maíz" ya está
    assert cliente.post("/cultivos", json={"nombre": "Poroto", "color": "rojo"}).status_code == 422
    r = cliente.put(f"/cultivos/{nuevo['id']}", json={"nombre": "Algodón", "color": "#123456"})
    assert r.json()["color"] == "#123456"
    assert cliente.delete(f"/cultivos/{nuevo['id']}").status_code == 204


def test_campanias_de_la_mas_nueva_a_la_mas_vieja(cliente):
    crear_campania(cliente, "2025/26")
    crear_campania(cliente, "2026/27")
    assert [c["nombre"] for c in cliente.get("/campanias").json()] == ["2026/27", "2025/26"]
    assert cliente.post("/campanias", json={"nombre": "2026/27"}).status_code == 409


def test_primera_y_segunda_en_la_misma_campania(cliente):
    lote = crear_lote(cliente)
    campania = crear_campania(cliente)
    trigo = sembrar(cliente, lote, campania, "Trigo", variedad="Baguette 620", fecha_siembra="2026-06-10")
    soja = sembrar(cliente, lote, campania, "Soja", ciclo="segunda", hectareas="80,5")
    assert (trigo["ciclo"], trigo["cultivo"], trigo["fecha_siembra"]) == ("primera", "Trigo", "2026-06-10")
    assert soja["hectareas"] == 80.5 and soja["color"]
    # Otra "primera" en el mismo lote y campaña: no (hay que editar la que está).
    r = cliente.post(f"/lotes/{lote['id']}/cultivos",
                     json={"campania_id": campania["id"], "cultivo_id": id_cultivo(cliente, "Maíz")})
    assert r.status_code == 409 and "Trigo" in r.json()["detail"]

    lotes = cliente.get(f"/lotes?campania_id={campania['id']}").json()
    assert [c["cultivo"] for c in lotes[0]["cultivos"]] == ["Trigo", "Soja"]
    assert cliente.get("/lotes").json()[0]["cultivos"] == []  # Sin campaña: no trae cultivos.
    ficha = cliente.get(f"/lotes/{lote['id']}").json()
    assert len(ficha["historial"]) == 2


def test_historial_de_varias_campanias(cliente):
    lote = crear_lote(cliente)
    vieja, nueva = crear_campania(cliente, "2025/26"), crear_campania(cliente, "2026/27")
    sembrar(cliente, lote, vieja, "Maíz", rinde="95,5")
    sembrar(cliente, lote, nueva, "Soja")
    historial = cliente.get(f"/lotes/{lote['id']}").json()["historial"]
    assert [(h["campania"], h["cultivo"]) for h in historial] == [("2026/27", "Soja"), ("2025/26", "Maíz")]
    assert historial[1]["rinde"] == 95.5


def test_editar_y_borrar_cultivo_del_lote(cliente):
    lote = crear_lote(cliente)
    campania = crear_campania(cliente)
    fila = sembrar(cliente, lote, campania, "Soja")
    cuerpo = {"campania_id": campania["id"], "cultivo_id": id_cultivo(cliente, "Maíz"),
              "fecha_siembra": "2026-10-01", "fecha_cosecha": "2027-03-20", "rinde": "110"}
    r = cliente.put(f"/lote-cultivos/{fila['id']}", json=cuerpo)
    assert r.status_code == 200, r.text
    assert (r.json()["cultivo"], r.json()["rinde"], r.json()["fecha_cosecha"]) == ("Maíz", 110, "2027-03-20")
    assert cliente.delete(f"/lote-cultivos/{fila['id']}").status_code == 204
    assert cliente.delete(f"/lote-cultivos/{fila['id']}").status_code == 404
    assert cliente.put(f"/lote-cultivos/{fila['id']}", json=cuerpo).status_code == 404


def test_cosecha_antes_de_la_siembra(cliente):
    lote = crear_lote(cliente)
    campania = crear_campania(cliente)
    r = cliente.post(f"/lotes/{lote['id']}/cultivos", json={
        "campania_id": campania["id"], "cultivo_id": id_cultivo(cliente, "Soja"),
        "fecha_siembra": "2026-11-01", "fecha_cosecha": "2026-10-01",
    })
    assert r.status_code == 422 and "cosecha" in r.text


def test_con_historial_no_se_borra_pero_se_archiva(cliente):
    lote = crear_lote(cliente)
    campania = crear_campania(cliente)
    sembrar(cliente, lote, campania, "Soja")
    assert cliente.delete(f"/lotes/{lote['id']}").status_code == 409
    assert cliente.delete(f"/campanias/{campania['id']}").status_code == 409
    assert cliente.delete(f"/cultivos/{id_cultivo(cliente, 'Soja')}").status_code == 409
    assert cliente.post(f"/lotes/{lote['id']}/archivar").status_code == 200


def test_cultivos_y_campanias_piden_login(cliente_anonimo):
    assert cliente_anonimo.get("/cultivos").status_code == 401
    assert cliente_anonimo.get("/campanias").status_code == 401
    assert cliente_anonimo.get("/lote-cultivos").status_code == 401
