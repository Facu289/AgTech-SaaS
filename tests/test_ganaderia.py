"""Tests de ganadería."""
from datetime import date, timedelta


def crear_animal(cliente, **datos):
    base = {"caravana": "1234", "categoria": "vaquillona", "raza": "Angus", "rodeo": "Norte"}
    r = cliente.post("/animales", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


def evento(cliente, animal_id, **datos):
    return cliente.post(f"/animales/{animal_id}/eventos", json=datos)


def test_caravana_repetida(cliente):
    crear_animal(cliente)
    assert cliente.post("/animales", json={"caravana": "1234", "categoria": "vaca"}).status_code == 409


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
    assert animal["categoria"] == "vaca"
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
    assert "máximo" in bot("/parto 1234 hhhhhh").lower()
    assert bot("/parto 1234 x").startswith("Formato")
    crear_animal(cliente, caravana="T1", categoria="toro")
    assert "no puede tener un parto" in bot("/parto T1 m")
