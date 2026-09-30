"""Tests del service programado por horas."""


def crear_maquina(cliente, **datos):
    base = {"nombre": "Tractor JD 6110", "tipo": "tractor", "horas_motor": 1000}
    r = cliente.post("/maquinas", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


def crear_plan(cliente, maquina_id, **datos):
    base = {"nombre": "Cambio de aceite", "cada_horas": 250}
    r = cliente.post(f"/maquinas/{maquina_id}/planes", json={**base, **datos})
    assert r.status_code == 201, r.text
    return r.json()


def test_plan_nuevo_arranca_desde_las_horas_actuales(cliente):
    m = crear_maquina(cliente)
    plan = crear_plan(cliente, m["id"])
    assert plan["ultima_horas"] == 1000
    assert plan["proximo"] == 1250 and plan["faltan"] == 250 and plan["estado"] == "ok"


def test_estados_segun_las_horas(cliente):
    m = crear_maquina(cliente)
    plan = crear_plan(cliente, m["id"], ultima_horas=800)  # Próximo a las 1050: faltan 50.
    assert plan["estado"] == "ok"
    cliente.post(f"/maquinas/{m['id']}/horas", json={"horas_motor": 1030})  # Faltan 20 (< 10% de 250).
    assert cliente.get("/services").json()[0]["estado"] == "proximo"
    cliente.post(f"/maquinas/{m['id']}/horas", json={"horas_motor": 1060})  # Pasado por 10.
    services = cliente.get("/alertas").json()["services"]
    assert services[0]["estado"] == "vencido" and services[0]["faltan"] == -10


def test_service_con_plan_reinicia_el_contador(cliente):
    m = crear_maquina(cliente)
    aceite = crear_plan(cliente, m["id"], ultima_horas=700)
    crear_plan(cliente, m["id"], nombre="Filtros", cada_horas=500, ultima_horas=700)
    r = cliente.post(f"/maquinas/{m['id']}/mantenimientos",
                     json={"descripcion": "Aceite", "horas": 1010, "planes": [aceite["id"]]})
    assert r.status_code == 201
    planes = {p["nombre"]: p for p in cliente.get(f"/maquinas/{m['id']}").json()["planes"]}
    assert planes["Cambio de aceite"]["ultima_horas"] == 1010  # Reiniciado.
    assert planes["Filtros"]["ultima_horas"] == 700  # No se tocó.


def test_plan_de_otra_maquina_no_se_puede_marcar(cliente):
    a = crear_maquina(cliente)
    b = crear_maquina(cliente, nombre="Otra")
    plan_b = crear_plan(cliente, b["id"])
    r = cliente.post(f"/maquinas/{a['id']}/mantenimientos", json={"descripcion": "x", "planes": [plan_b["id"]]})
    assert r.status_code == 404
    # Y como falló, no se guardó el service (todo en la misma transacción).
    assert cliente.get(f"/maquinas/{a['id']}").json()["mantenimientos"] == []


def test_trilla_solo_para_cosechadoras(cliente):
    m = crear_maquina(cliente)
    r = cliente.post(f"/maquinas/{m['id']}/planes", json={"nombre": "Cóncavo", "cada_horas": 300, "medida": "trilla"})
    assert r.status_code == 400
    cose = crear_maquina(cliente, nombre="Cose", tipo="cosechadora", horas_trilla=500)
    plan = crear_plan(cliente, cose["id"], nombre="Cóncavo", cada_horas=300, medida="trilla")
    assert plan["ultima_horas"] == 500


def test_nombre_de_plan_repetido(cliente):
    m = crear_maquina(cliente)
    crear_plan(cliente, m["id"])
    r = cliente.post(f"/maquinas/{m['id']}/planes", json={"nombre": "cambio de ACEITE", "cada_horas": 100})
    assert r.status_code == 409


def test_editar_y_desactivar_plan(cliente):
    m = crear_maquina(cliente)
    plan = crear_plan(cliente, m["id"])
    r = cliente.put(f"/planes/{plan['id']}", json={"nombre": "Aceite motor", "cada_horas": "300", "activo": False})
    assert r.json()["cada_horas"] == 300 and r.json()["ultima_horas"] == 1000  # Vacío = no se toca.
    assert cliente.get("/services").json() == []  # Desactivado: no aparece.


def test_maquina_con_planes_no_se_puede_borrar(cliente):
    m = crear_maquina(cliente)
    crear_plan(cliente, m["id"])
    assert cliente.delete(f"/maquinas/{m['id']}").status_code == 409


def test_listado_trae_el_service_mas_urgente(cliente):
    m = crear_maquina(cliente)
    crear_plan(cliente, m["id"], nombre="Filtros", cada_horas=500)
    crear_plan(cliente, m["id"], nombre="Engrase", cada_horas=50)
    assert cliente.get("/maquinas").json()[0]["proximo_service"]["nombre"] == "Engrase"


# ---------- Telegram ----------

def test_telegram_service_reinicia_el_plan_nombrado(bot, cliente):
    m = crear_maquina(cliente)
    crear_plan(cliente, m["id"], ultima_horas=600)
    crear_plan(cliente, m["id"], nombre="Filtros", cada_horas=500, ultima_horas=600)
    respuesta = bot("/service jd - cambio de aceite")
    assert "Plan reiniciado: Cambio de aceite" in respuesta
    planes = {p["nombre"]: p for p in cliente.get("/services").json()}
    assert planes["Cambio de aceite"]["ultima_horas"] == 1000 and planes["Filtros"]["ultima_horas"] == 600
    assert "Filtros" in bot("/service jd - todo")
    assert "No marqué ningún plan" in bot("/service jd - lavado")


def test_telegram_services_y_alertas(bot, cliente):
    m = crear_maquina(cliente)
    crear_plan(cliente, m["id"], ultima_horas=700)  # Toca a las 950: pasado por 50.
    assert "🔴 Cambio de aceite" in bot("/services")
    assert "pasado por 50 h" in bot("/alertas")
    assert "Próximo: 🔴" in bot("/maquinas")
