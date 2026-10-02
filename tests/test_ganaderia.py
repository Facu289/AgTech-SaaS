"""Tests de ganadería."""
from datetime import date, timedelta


def categoria_id(cliente, nombre, especie="Vacuno"):
    """Busca el id de una categoría por su nombre (ej: "vaca" de Vacuno)."""
    for e in cliente.get("/especies").json():
        if e["nombre"] == especie:
            return next(c["id"] for c in e["categorias"] if c["nombre"].lower() == nombre.lower())
    raise AssertionError(f"No existe la especie {especie}")


def crear_animal(cliente, categoria="vaquillona", especie="Vacuno", **datos):
    base = {"caravana": "1234", "categoria_id": categoria_id(cliente, categoria, especie), "raza": "Angus", "rodeo": "Norte"}
    r = cliente.post("/animales", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


def evento(cliente, animal_id, **datos):
    return cliente.post(f"/animales/{animal_id}/eventos", json=datos)


def test_caravana_repetida_pide_confirmacion(cliente):
    crear_animal(cliente)
    nueva = {"caravana": "1234", "categoria_id": categoria_id(cliente, "vaca")}
    r = cliente.post("/animales", json=nueva)
    assert r.status_code == 409 and r.json()["caravana_repetida"] is True
    assert "Vacuno (vaquillona)" in r.json()["detail"]
    # Confirmando, se guarda igual.
    assert cliente.post("/animales", json={**nueva, "confirmar_repetida": True}).status_code == 201


def test_macho_no_tiene_estado_reproductivo(cliente):
    toro = crear_animal(cliente, caravana="T1", categoria="toro", estado_reproductivo="prenada")
    assert toro["estado_reproductivo"] == ""
    r = evento(cliente, toro["id"], tipo="parto", crias_machos=1)
    assert r.status_code == 400


def test_tacto_con_servicio_calcula_fecha_de_parto(cliente):
    vaca = crear_animal(cliente)
    servicio = date.today() - timedelta(days=60)
    evento(cliente, vaca["id"], tipo="servicio", fecha=servicio.isoformat(), detalle="toro 55")
    r = evento(cliente, vaca["id"], tipo="tacto", resultado="Preñada")
    animal = r.json()
    assert animal["estado_reproductivo"] == "prenada"
    assert animal["fecha_probable_parto"] == (servicio + timedelta(days=283)).isoformat()


def test_parto_vaquillona_pasa_a_vaca_y_queda_vacia(cliente):
    vaq = crear_animal(cliente, estado_reproductivo="prenada", fecha_probable_parto=date.today().isoformat())
    r = evento(cliente, vaq["id"], tipo="parto", crias_machos=1, crias_hembras=1, detalle="mellizos")
    animal = r.json()
    assert animal["categoria"] == "Vaca"
    assert animal["estado_reproductivo"] == "vacia"
    assert animal["fecha_probable_parto"] is None
    assert animal["partos"] == 1


def test_parto_sin_crias_se_rechaza(cliente):
    vaca = crear_animal(cliente, categoria="vaca")
    r = evento(cliente, vaca["id"], tipo="parto")
    assert r.status_code == 400 and "crías" in r.json()["detail"]


def test_crias_con_madre(cliente):
    madre = crear_animal(cliente, categoria="vaca")
    cria = crear_animal(cliente, caravana="1234-A", categoria="ternera", madre_id=madre["id"])
    assert cria["madre_caravana"] == "1234"
    ficha = cliente.get(f"/animales/{madre['id']}").json()
    assert [c["caravana"] for c in ficha["crias"]] == ["1234-A"]
    # La madre tiene cría: no se puede borrar.
    assert cliente.delete(f"/animales/{madre['id']}").status_code == 409


def test_baja_no_admite_eventos(cliente):
    vaca = crear_animal(cliente, categoria="vaca")
    cliente.put(f"/animales/{vaca['id']}", json={**vaca, "estado": "vendido"})
    assert evento(cliente, vaca["id"], tipo="sanidad", detalle="vacuna").status_code == 409
    assert cliente.get("/animales").json() == []


def test_alerta_de_parto(cliente):
    pronto = (date.today() + timedelta(days=5)).isoformat()
    crear_animal(cliente, categoria="vaca", estado_reproductivo="prenada", fecha_probable_parto=pronto)
    crear_animal(cliente, caravana="99", categoria="vaca", estado_reproductivo="prenada",
                 fecha_probable_parto=(date.today() + timedelta(days=90)).isoformat())
    partos = cliente.get("/alertas").json()["partos"]
    assert [p["caravana"] for p in partos] == ["1234"]


# ---------- Telegram ----------

def test_telegram_flujo_reproductivo(bot, cliente):
    crear_animal(cliente)
    assert "preñada" in bot("/tacto 1234 preñada 15/03/2030")
    assert "15/03/2030" in bot("/animal 1234")
    respuesta = bot("/parto 1234 mh - parto difícil")
    assert "mellizos: 1 macho y 1 hembra" in respuesta
    assert "vaquillona a vaca" in respuesta
    assert "vacía" in bot("/animal 1234").lower()


def test_telegram_resumen_y_filtros(bot, cliente):
    crear_animal(cliente, caravana="1", categoria="vaca", estado_reproductivo="prenada")
    crear_animal(cliente, caravana="2", categoria="vaca", estado_reproductivo="vacia", rodeo="Sur")
    crear_animal(cliente, caravana="3", categoria="toro")
    resumen = bot("/animales")
    assert "3 animales" in resumen and "1 preñadas · 1 vacías" in resumen
    assert "• 1 " in bot("/animales preñadas") and "• 2 " not in bot("/animales preñadas")
    assert "• 2 " in bot("/animales sur")
    assert "• 3 " in bot("/animales toros")


def test_telegram_caravana_exacta(bot, cliente):
    crear_animal(cliente, caravana="1234")
    respuesta = bot("/parto 123 h")
    assert "No encontré" in respuesta and "1234" in respuesta  # Sugiere, pero no adivina.
    assert "máximo" in bot("/parto 1234 " + "h" * 21).lower()
    assert bot("/parto 1234 x").startswith("Formato")
    crear_animal(cliente, caravana="T1", categoria="toro")
    assert "no puede tener un parto" in bot("/parto T1 m")


# ---------- Especies, categorías y grupos ----------

def crear_especie(cliente, nombre, dias_gestacion=None, categorias=()):
    """Crea una especie con sus categorías: categorias = [("Oveja", "hembra"), ...]."""
    r = cliente.post("/especies", json={"nombre": nombre, "dias_gestacion": dias_gestacion})
    assert r.status_code == 201, r.text
    for nombre_categoria, sexo in categorias:
        r2 = cliente.post(f"/especies/{r.json()['id']}/categorias", json={"nombre": nombre_categoria, "sexo": sexo})
        assert r2.status_code == 201, r2.text
    return r.json()


def test_vacuno_viene_cargado(cliente):
    vacuno = cliente.get("/especies").json()[0]
    assert (vacuno["nombre"], vacuno["dias_gestacion"]) == ("Vacuno", 283)
    assert [c["nombre"] for c in vacuno["categorias"] if c["sexo"] == "hembra"] == ["Vaca", "Vaquillona", "Ternera"]


def test_especie_nueva_usa_sus_dias_de_gestacion(cliente):
    crear_especie(cliente, "Ovino", 150, [("Oveja", "hembra"), ("Carnero", "macho")])
    oveja = crear_animal(cliente, "oveja", "Ovino", caravana="O1")
    assert oveja["especie"] == "Ovino" and oveja["reproductiva"]
    servicio = date(2026, 3, 1)
    evento(cliente, oveja["id"], tipo="servicio", fecha=servicio.isoformat())
    animal = evento(cliente, oveja["id"], tipo="tacto", resultado="prenada").json()
    assert animal["fecha_probable_parto"] == (servicio + timedelta(days=150)).isoformat()
    # El parto de una oveja no le cambia la categoría (eso es solo vaquillona -> vaca).
    animal = evento(cliente, oveja["id"], tipo="parto", crias_hembras=2).json()
    assert animal["categoria"] == "Oveja" and animal["estado_reproductivo"] == "vacia"


def test_especie_sin_gestacion_no_tiene_partos(cliente):
    crear_especie(cliente, "Gallina", None, [("Ponedora", "hembra")])
    gallina = crear_animal(cliente, "ponedora", "Gallina", caravana="G1", estado_reproductivo="prenada")
    assert not gallina["reproductiva"] and gallina["estado_reproductivo"] == ""
    r = evento(cliente, gallina["id"], tipo="tacto", resultado="prenada")
    assert r.status_code == 400 and "días de gestación" in r.json()["detail"]
    assert evento(cliente, gallina["id"], tipo="sanidad", detalle="vacuna Newcastle").status_code == 201


def test_grupo_de_animales(cliente):
    crear_especie(cliente, "Gallina", None, [("Ponedora", "hembra")])
    grupo = crear_animal(cliente, "ponedora", "Gallina", caravana="Galpón 1", es_grupo=True, cantidad=120)
    assert (grupo["es_grupo"], grupo["cantidad"]) == (1, 120)
    especie = next(e for e in cliente.get("/especies").json() if e["nombre"] == "Gallina")
    assert especie["cabezas"] == 120
    # Un animal suelto siempre cuenta 1, aunque se mande otra cantidad.
    suelta = crear_animal(cliente, "ponedora", "Gallina", caravana="G7", cantidad=50)
    assert suelta["cantidad"] == 1
    # Un grupo de vacas no puede tener tacto (se hace animal por animal).
    rodeo = crear_animal(cliente, "vaca", caravana="Rodeo cría", es_grupo=True, cantidad=40)
    r = evento(cliente, rodeo["id"], tipo="tacto", resultado="prenada")
    assert r.status_code == 400 and "es un grupo" in r.json()["detail"]


def test_madre_de_otra_especie_se_rechaza(cliente):
    vaca = crear_animal(cliente, "vaca")
    crear_especie(cliente, "Ovino", 150, [("Cordero", "macho")])
    r = cliente.post("/animales", json={"caravana": "C1", "categoria_id": categoria_id(cliente, "cordero", "Ovino"),
                                        "madre_id": vaca["id"]})
    assert r.status_code == 400 and "otra especie" in r.json()["detail"]


def test_no_se_borra_especie_ni_categoria_en_uso(cliente):
    ovino = crear_especie(cliente, "Ovino", 150, [("Oveja", "hembra"), ("Borrega", "hembra")])
    crear_animal(cliente, "oveja", "Ovino", caravana="O1")
    assert cliente.delete(f"/especies/{ovino['id']}").status_code == 409
    assert cliente.delete(f"/categorias-animal/{categoria_id(cliente, 'oveja', 'Ovino')}").status_code == 409
    # La que nadie usa sí se puede borrar.
    assert cliente.delete(f"/categorias-animal/{categoria_id(cliente, 'borrega', 'Ovino')}").status_code == 204
    # Y una especie sin animales también.
    llama = crear_especie(cliente, "Llama", 345, [("Hembra", "hembra")])
    assert cliente.delete(f"/especies/{llama['id']}").status_code == 204


def test_especie_repetida(cliente):
    crear_especie(cliente, "Porcino", 114)
    assert cliente.post("/especies", json={"nombre": "porcino"}).status_code == 409


def test_telegram_caravana_repetida_pide_especie(bot, cliente):
    crear_animal(cliente, "vaca", caravana="12")
    crear_especie(cliente, "Ovino", 150, [("Oveja", "hembra")])
    crear_animal(cliente, "oveja", "Ovino", caravana="12", confirmar_repetida=True)
    respuesta = bot("/tacto 12 preñada")
    assert "Hay 2 animales" in respuesta and "ovino 12" in respuesta  # No adivina.
    assert "Tacto registrado" in bot("/tacto ovino 12 preñada")
    assert "Especie: Ovino" in bot("/animal ovinos 12")
    assert "• 12 — oveja (Ovino)" in bot("/animales ovinos")


# ---------- Resumen de crías ----------

def test_nacimientos_y_resumen_de_crias(bot, cliente):
    crear_especie(cliente, "Ovino", 150, [("Oveja", "hembra"), ("Cordero", "macho")])
    oveja = crear_animal(cliente, "oveja", "Ovino", caravana="O1")
    vaca = crear_animal(cliente, "vaca", caravana="V1")
    hoy = date.today()
    evento(cliente, oveja["id"], tipo="parto", crias_machos=1, crias_hembras=1, fecha=hoy.isoformat())
    evento(cliente, vaca["id"], tipo="aborto", fecha=hoy.isoformat())
    # Una cría cargada con caravana, hija de la oveja: cuenta como "con caravana".
    crear_animal(cliente, "cordero", "Ovino", caravana="O1-A", madre_id=oveja["id"], fecha_nacimiento=hoy.isoformat())

    nacimientos = cliente.get("/nacimientos").json()
    assert {(n["tipo"], n["especie"], n["madre_caravana"]) for n in nacimientos} == {("parto", "Ovino", "O1"), ("aborto", "Vacuno", "V1")}
    parto = next(n for n in nacimientos if n["tipo"] == "parto")
    assert (parto["crias_machos"], parto["crias_hembras"], parto["crias_con_caravana"]) == (1, 1, 1)

    resumen = bot("/crias")
    assert "Ovino: 1 partos → 2 crías (1 machos, 1 hembras)" in resumen
    assert "1 mellizos o más" in resumen and "1 abortos" in resumen
    assert "Vacuno" not in bot("/crias ovinos")
    assert "No encontré la especie" in bot("/crias jirafa")
