"""Tests de órdenes de trabajo: cargar, advertir falta de stock, descontar y devolver."""
import pytest


def crear_quimico(cliente, nombre, cantidad, unidad="litros"):
    r = cliente.post("/insumos", json={"nombre": nombre, "categoria": "agroquimico", "unidad": unidad, "cantidad": cantidad})
    assert r.status_code == 201, r.text
    return r.json()


def orden_terrestre(glifosato, coady, **cambios):
    """La orden 1-033 de la planilla (simplificada a 2 productos)."""
    datos = {
        "numero": "1-033", "campo": "LM", "tarea": "pulverizacion_terrestre", "operarios": "A. Arnaudo",
        "fecha_emision": "2026-10-01", "estado_lote": "Maíz", "caldo_ha": "30", "tancadas": 2,
        "descripcion": "Barbecho",
        "lotes": [{"lote": "31+32", "hectareas": 47}, {"lote": "37", "hectareas": 35},
                  {"lote": "44N", "hectareas": "8,6"}, {"lote": "44S", "hectareas": 69},
                  {"lote": "45", "hectareas": "22,7"}],
        "productos": [{"insumo_id": glifosato["id"], "cantidad_total": 380},
                      {"insumo_id": coady["id"], "cantidad_total": 6}],
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def stock(cliente):
    return crear_quimico(cliente, "Glifosato 66,2% - POWER PLUS II", 500), crear_quimico(cliente, "Coady. HYDROP 360", 10)


def crear_orden(cliente, datos):
    r = cliente.post("/ordenes", json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def stock_de(cliente, insumo):
    return next(i["cantidad"] for i in cliente.get("/insumos").json() if i["id"] == insumo["id"])


# ---------- Cargar ----------

def test_crear_orden_calcula_hectareas_y_dosis(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady))
    assert orden["estado"] == "pendiente"
    assert orden["hectareas"] == pytest.approx(182.3)
    glifo = orden["productos"][0]
    assert glifo["insumo"].startswith("Glifosato")
    assert glifo["dosis_ha"] == pytest.approx(380 / 182.3)  # 2,084 l/ha, como en la planilla.
    assert glifo["por_tancada"] == 190
    assert orden["advertencias"] == []
    # Cargar la orden NO toca el stock.
    assert stock_de(cliente, glifosato) == 500


def test_advertencia_si_no_alcanza_el_stock(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady, productos=[
        {"insumo_id": glifosato["id"], "cantidad_total": 600}, {"insumo_id": coady["id"], "cantidad_total": 6},
    ]))
    # Se guarda igual (la orden se emite antes de aplicar), pero avisa.
    assert len(orden["advertencias"]) == 1
    assert "Glifosato" in orden["advertencias"][0] and "hay 500" in orden["advertencias"][0]


def test_validaciones(cliente, stock):
    glifosato, coady = stock
    assert cliente.post("/ordenes", json=orden_terrestre(glifosato, coady, tarea="cosecha")).status_code == 422
    sin_ha = orden_terrestre(glifosato, coady, lotes=[{"lote": "37", "hectareas": 0}])
    assert cliente.post("/ordenes", json=sin_ha).status_code == 422
    no_existe = orden_terrestre(glifosato, coady, productos=[{"insumo_id": 999, "cantidad_total": 1}])
    assert cliente.post("/ordenes", json=no_existe).status_code == 400


def test_siguiente_numero(cliente, stock):
    assert cliente.get("/ordenes/siguiente-numero").json()["numero"] == ""
    crear_orden(cliente, orden_terrestre(*stock, numero="1-033"))
    assert cliente.get("/ordenes/siguiente-numero").json()["numero"] == "1-034"
    crear_orden(cliente, orden_terrestre(*stock, numero="1-099"))
    assert cliente.get("/ordenes/siguiente-numero").json()["numero"] == "1-100"


# ---------- Realizar: descontar el stock ----------

def test_realizar_descuenta_y_volver_a_pendiente_devuelve(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady))
    r = cliente.post(f"/ordenes/{orden['id']}/realizar", json={"fecha_realizacion": "2026-10-03"})
    assert r.status_code == 200, r.text
    assert (r.json()["estado"], r.json()["fecha_realizacion"]) == ("realizada", "2026-10-03")
    assert stock_de(cliente, glifosato) == 120 and stock_de(cliente, coady) == 4

    # Queda en Movimientos como salida, con el número de orden.
    salidas = [m for m in cliente.get("/movimientos").json() if m["tipo"] == "salida"]
    assert len(salidas) == 2 and all("OT 1-033" in m["motivo"] and "LM" in m["motivo"] for m in salidas)
    assert salidas[0]["fecha"].startswith("2026-10-03")
    assert len(cliente.get(f"/ordenes/{orden['id']}").json()["movimientos"]) == 2

    # Realizada no se edita ni se realiza dos veces.
    assert cliente.put(f"/ordenes/{orden['id']}", json=orden_terrestre(glifosato, coady)).status_code == 409
    assert cliente.post(f"/ordenes/{orden['id']}/realizar", json={}).status_code == 409

    # Volver a pendiente devuelve el stock (con entradas: el historial queda).
    r = cliente.post(f"/ordenes/{orden['id']}/pendiente")
    assert r.json()["estado"] == "pendiente" and r.json()["fecha_realizacion"] is None
    assert stock_de(cliente, glifosato) == 500 and stock_de(cliente, coady) == 10
    assert len(cliente.get(f"/ordenes/{orden['id']}").json()["movimientos"]) == 4


def test_si_falta_un_producto_no_descuenta_ninguno(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady, productos=[
        {"insumo_id": glifosato["id"], "cantidad_total": 100}, {"insumo_id": coady["id"], "cantidad_total": 50},
    ]))
    r = cliente.post(f"/ordenes/{orden['id']}/realizar", json={})
    assert r.status_code == 409
    assert "Coady" in r.json()["detail"] and "no se descontó nada" in r.json()["detail"]
    assert stock_de(cliente, glifosato) == 500  # Ni siquiera el que alcanzaba.
    assert cliente.get(f"/ordenes/{orden['id']}").json()["estado"] == "pendiente"


def test_producto_repetido_suma(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady, productos=[
        {"insumo_id": glifosato["id"], "cantidad_total": 300}, {"insumo_id": glifosato["id"], "cantidad_total": 300},
    ]))
    assert len(orden["advertencias"]) == 1  # 600 > 500 aunque cada fila sola alcance.
    assert cliente.post(f"/ordenes/{orden['id']}/realizar", json={}).status_code == 409


# ---------- Anular, eliminar ----------

def test_anular_reactivar_y_eliminar(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady))
    assert cliente.post(f"/ordenes/{orden['id']}/anular").json()["estado"] == "anulada"
    assert cliente.post(f"/ordenes/{orden['id']}/realizar", json={}).status_code == 409
    assert cliente.post(f"/ordenes/{orden['id']}/reactivar").json()["estado"] == "pendiente"
    assert cliente.delete(f"/ordenes/{orden['id']}").status_code == 204  # Nunca movió stock.
    assert cliente.get(f"/ordenes/{orden['id']}").status_code == 404


def test_una_orden_que_movio_stock_no_se_elimina(cliente, stock):
    glifosato, coady = stock
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady))
    cliente.post(f"/ordenes/{orden['id']}/realizar", json={})
    assert cliente.delete(f"/ordenes/{orden['id']}").status_code == 409
    cliente.post(f"/ordenes/{orden['id']}/pendiente")
    assert cliente.delete(f"/ordenes/{orden['id']}").status_code == 409  # Su historial queda: se anula.
    assert cliente.post(f"/ordenes/{orden['id']}/anular").status_code == 200


# ---------- Lotes de la orden y registro por lote ----------

def test_desarmar_lotes(app):
    from app.ordenes.rutas import desarmar_lotes
    assert desarmar_lotes("31+32") == ["31", "32"]
    assert desarmar_lotes("1 Al 12") == [str(n) for n in range(1, 13)]
    assert desarmar_lotes("44N") == ["44N"]
    assert desarmar_lotes("3 a 5, 7") == ["3", "4", "5", "7"]
    assert desarmar_lotes("La Loma") == ["La Loma"]


def test_registro_por_lote(cliente, stock):
    """Cada lote del mapa que está en la orden recibe: dosis/ha de la orden × sus hectáreas."""
    glifosato, coady = stock
    from test_lotes import cuadrado

    for campo, nombre, latitud in (("LM", "31", -30.0), ("LM", "32", -30.02), ("SR Oeste", "31", -31.0)):
        r = cliente.post("/lotes", json={"campo": campo, "nombre": nombre, "geometria": cuadrado(latitud=latitud),
                                         "hectareas": "20"})
        assert r.status_code == 201, r.text
    orden = crear_orden(cliente, orden_terrestre(glifosato, coady))
    assert [l["nombre"] for l in orden["lotes_mapa"]] == ["31", "32"]
    assert orden["lotes_sin_vincular"] == ["37", "44N", "44S", "45"]  # No están en el mapa: se avisan.

    # El "31" de SR Oeste no es de esta orden (la orden es del campo LM).
    otro_31 = next(l for l in cliente.get("/lotes").json() if l["campo"] == "SR Oeste")
    assert cliente.get(f"/lotes/{otro_31['id']}/aplicaciones").json() == []
    lote_31 = next(l for l in cliente.get("/lotes").json() if l["nombre"] == "31" and l["campo"] == "LM")
    aplicaciones = cliente.get(f"/lotes/{lote_31['id']}/aplicaciones").json()
    assert len(aplicaciones) == 1 and aplicaciones[0]["numero"] == "1-033"
    glifo = aplicaciones[0]["productos"][0]
    assert glifo["dosis_ha"] == pytest.approx(380 / 182.3)
    assert glifo["cantidad"] == pytest.approx(380 / 182.3 * 20)  # Lo que le tocó a ESE lote.

    # Una orden anulada no cuenta en el registro del lote.
    cliente.post(f"/ordenes/{orden['id']}/anular")
    assert cliente.get(f"/lotes/{lote_31['id']}/aplicaciones").json() == []


def test_numero_con_cero_adelante_es_decimal(app):
    """'0.375' es una dosis (0,375), no 375 con punto de miles."""
    from app.nucleo.utilidades import leer_numero
    assert leer_numero("0.375") == 0.375
    assert leer_numero("1.500") == 1500
    assert leer_numero("0,375") == 0.375


def test_ordenes_piden_login(cliente_anonimo):
    assert cliente_anonimo.get("/ordenes").status_code == 401
    assert cliente_anonimo.post("/ordenes", json={}).status_code == 401
