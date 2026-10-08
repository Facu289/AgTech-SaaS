"""Última actividad (Inicio): lo último que se cargó, mezclado y del más nuevo al más viejo."""


def test_sin_nada_cargado(cliente):
    assert cliente.get("/actividad").json() == []


def test_junta_todo_y_ordena_del_mas_nuevo(cliente, bot):
    bot("/nuevo glifosato herbicida litros")
    bot("/entrada 100 glifosato - compra")
    maquina = cliente.post("/maquinas", json={"nombre": "JD 6110", "tipo": "tractor"}).json()
    cliente.post(f"/maquinas/{maquina['id']}/trabajos", json={"tipo": "siembra", "hectareas": "50", "lote": "La Loma"})
    insumo = cliente.get("/insumos").json()[0]
    orden = cliente.post("/ordenes", json={
        "numero": "1-040", "campo": "LM", "tarea": "pulverizacion_dron",
        "lotes": [{"lote": "1 al 3", "hectareas": 30}], "productos": [{"insumo_id": insumo["id"], "cantidad_total": 10}],
    }).json()
    cliente.post(f"/ordenes/{orden['id']}/realizar", json={})

    actividad = cliente.get("/actividad").json()
    titulos = [a["titulo"] for a in actividad]
    assert "OT 1-040 realizada" in titulos and "OT 1-040 cargada" in titulos
    assert "Entrada de glifosato" in titulos
    assert "Siembra · JD 6110" in titulos
    # La salida de stock de la orden NO se repite como movimiento suelto (ya está como "orden realizada").
    assert not any(t.startswith("Salida de glifosato") for t in titulos)
    # Del más nuevo al más viejo.
    momentos = [a["momento"] for a in actividad]
    assert momentos == sorted(momentos, reverse=True)
    assert all(a["enlace"] for a in actividad)


def test_limite(cliente, bot):
    bot("/nuevo urea fertilizante kg")
    for _ in range(5):
        bot("/entrada 1 urea")
    assert len(cliente.get("/actividad?limite=3").json()) == 3
    assert cliente.get("/actividad?limite=0").status_code == 422


def test_actividad_pide_login(cliente_anonimo):
    assert cliente_anonimo.get("/actividad").status_code == 401


def test_alerta_de_orden_sin_stock(cliente, bot):
    bot("/nuevo glifosato herbicida litros")
    bot("/entrada 10 glifosato")
    insumo = cliente.get("/insumos").json()[0]
    cliente.post("/ordenes", json={
        "numero": "1-050", "tarea": "pulverizacion_terrestre", "lotes": [{"lote": "5", "hectareas": 10}],
        "productos": [{"insumo_id": insumo["id"], "cantidad_total": 50}],
    })
    pendientes = cliente.get("/alertas").json()["ordenes_pendientes"]
    assert len(pendientes) == 1 and pendientes[0]["faltantes"] == ["glifosato"]
    assert "OT 1-050: falta glifosato" in bot("/alertas")
