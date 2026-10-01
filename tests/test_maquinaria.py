"""Tests de maquinaria."""
from datetime import date, timedelta


def crear_maquina(cliente, **datos):
    base = {"nombre": "Tractor JD 6110", "tipo": "tractor", "marca": "John Deere", "horas_motor": "1.500"}
    r = cliente.post("/maquinas", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_y_ficha(cliente):
    maquina = crear_maquina(cliente, anio="")  # Año vacío desde el formulario = sin dato.
    assert maquina["horas_motor"] == 1500 and maquina["anio"] is None
    ficha = cliente.get(f"/maquinas/{maquina['id']}").json()
    assert ficha["maquina"]["nombre"] == "Tractor JD 6110"
    assert ficha["mantenimientos"] == [] and ficha["trabajos"] == []


def test_nombre_repetido(cliente):
    crear_maquina(cliente)
    r = cliente.post("/maquinas", json={"nombre": "tractor jd 6110", "tipo": "tractor"})
    assert r.status_code == 409


def test_horas_trilla_solo_cosechadoras(cliente):
    tractor = crear_maquina(cliente, horas_trilla=100)
    assert tractor["horas_trilla"] is None
    cose = crear_maquina(cliente, nombre="Cose", tipo="cosechadora", horas_trilla=800)
    assert cose["horas_trilla"] == 800


def test_service_actualiza_horometro(cliente):
    m = crear_maquina(cliente)
    r = cliente.post(f"/maquinas/{m['id']}/mantenimientos",
                     json={"tipo": "service", "horas": 1600, "descripcion": "Aceite y filtros", "costo": "85.000"})
    assert r.status_code == 201
    # Campos opcionales vacíos (como llegan de un formulario) = sin dato.
    r = cliente.post(f"/maquinas/{m['id']}/mantenimientos",
                     json={"tipo": "arreglo", "horas": "", "descripcion": "Luz trasera", "costo": ""})
    assert r.status_code == 201 and r.json()["costo"] is None
    assert cliente.post(f"/maquinas/{m['id']}/mantenimientos",
                        json={"descripcion": "x", "costo": "-5"}).status_code == 422
    ficha = cliente.get(f"/maquinas/{m['id']}").json()
    assert ficha["maquina"]["horas_motor"] == 1600
    assert ficha["maquina"]["horas_ultimo_service"] == 1600
    assert ficha["mantenimientos"][-1]["costo"] == 85000


def test_actualizar_horas(cliente):
    m = crear_maquina(cliente, nombre="Cose", tipo="cosechadora", horas_trilla=100)
    r = cliente.post(f"/maquinas/{m['id']}/horas", json={"horas_motor": "1.450,5", "horas_trilla": ""})
    assert r.json()["horas_motor"] == 1450.5
    assert r.json()["horas_trilla"] == 100  # Vacío = no se toca.


def test_trabajos_suman_hectareas(cliente):
    m = crear_maquina(cliente, nombre="Cose", tipo="cosechadora")
    for ha in (100, "50,5"):
        cliente.post(f"/maquinas/{m['id']}/trabajos", json={"tipo": "trilla", "hectareas": ha, "lote": "4"})
    assert cliente.get("/maquinas").json()[0]["hectareas_totales"] == 150.5
    r = cliente.post(f"/maquinas/{m['id']}/trabajos", json={"tipo": "trilla", "hectareas": 0})
    assert r.status_code == 422


def test_eliminar_o_archivar(cliente):
    vacia = crear_maquina(cliente, nombre="Vacía")
    assert cliente.delete(f"/maquinas/{vacia['id']}").status_code == 204
    usada = crear_maquina(cliente)
    cliente.post(f"/maquinas/{usada['id']}/trabajos", json={"tipo": "siembra", "hectareas": 10})
    assert cliente.delete(f"/maquinas/{usada['id']}").status_code == 409
    assert cliente.post(f"/maquinas/{usada['id']}/archivar").status_code == 200
    assert cliente.get("/maquinas").json() == []


def test_vencimientos_y_alertas(cliente):
    m = crear_maquina(cliente)
    pronto = (date.today() + timedelta(days=10)).isoformat()
    lejos = (date.today() + timedelta(days=200)).isoformat()
    cliente.post("/vencimientos", json={"descripcion": "Seguro", "tipo": "seguro",
                                        "fecha_vencimiento": pronto, "maquina_id": m["id"]})
    cliente.post("/vencimientos", json={"descripcion": "Licencia drone", "tipo": "licencia",
                                        "fecha_vencimiento": lejos, "maquina_id": ""})
    alertas = cliente.get("/alertas").json()["vencimientos"]
    assert [v["descripcion"] for v in alertas] == ["Seguro"]
    assert alertas[0]["dias"] == 10



def test_serie_del_monitor_en_licencias_y_suscripciones(cliente, bot):
    """El N° de serie del monitor se carga en la máquina y aparece en sus licencias, no en el seguro."""
    m = crear_maquina(cliente, nombre="Sembradora Pla", tipo="sembradora", serie_monitor="  PCG-12345 ")
    assert m["serie_monitor"] == "PCG-12345"  # Sin espacios de más.
    pronto = (date.today() + timedelta(days=5)).isoformat()
    for descripcion, tipo in [("Piloto automático", "licencia"), ("Corte por sección", "licencia"),
                              ("Seguimiento satelital", "suscripcion"), ("Seguro", "seguro")]:
        r = cliente.post("/vencimientos", json={"descripcion": descripcion, "tipo": tipo,
                                                "fecha_vencimiento": pronto, "maquina_id": m["id"]})
        assert r.status_code == 201, r.text
    vencimientos = {v["descripcion"]: v for v in cliente.get("/vencimientos").json()}
    assert vencimientos["Corte por sección"]["maquina_serie_monitor"] == "PCG-12345"
    respuesta = bot("/vencimientos")
    assert "Piloto automático (Sembradora Pla · monitor PCG-12345)" in respuesta
    assert "Seguimiento satelital (Sembradora Pla · monitor PCG-12345)" in respuesta
    assert "Seguro (Sembradora Pla)" in respuesta  # El seguro no tiene que ver con el monitor.


def test_contactos(cliente):
    r = cliente.post("/contactos", json={"nombre": "Pedro", "rubro": "mecanico", "telefono": "3584 123456"})
    assert r.status_code == 201
    contacto = r.json()
    cliente.put(f"/contactos/{contacto['id']}", json={**contacto, "empresa": "Taller Pedro"})
    assert cliente.get("/contactos").json()[0]["empresa"] == "Taller Pedro"


# ---------- Telegram ----------

def test_telegram_horas_trabajo_service(bot, cliente):
    crear_maquina(cliente)
    assert "1.520 h" in bot("/horas jd 6110 1520")
    assert "menos" in bot("/horas jd 6110 100")  # No deja bajar horas por error.
    assert "120 ha en lote 4" in bot("/trabajo jd 120 siembra - lote 4")
    assert "Service registrado" in bot("/service jd 6110 - aceite")
    respuesta = bot("/maquinas")
    assert "1.520 h" in respuesta and "Último service" in respuesta


def test_telegram_maquina_inexistente(bot, cliente):
    crear_maquina(cliente)
    assert "¿Quisiste decir: Tractor JD 6110?" in bot("/horas tractor jd 6100 1520")
    assert "No encontré" in bot("/horas zzz 10")
    crear_maquina(cliente, nombre="Tractor JD 7200")
    assert "varias coincidencias" in bot("/horas tractor jd 1600")
