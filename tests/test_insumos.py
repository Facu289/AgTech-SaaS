"""Tests de insumos, movimientos y comandos de stock en Telegram."""


def crear(cliente, **datos):
    base = {"nombre": "Urea", "categoria": "fertilizante", "unidad": "kg"}
    respuesta = cliente.post("/insumos", json={**base, **datos})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# ---------- API ----------

def test_crear_con_subcategoria(cliente):
    insumo = crear(cliente, nombre="Glifosato", categoria="agroquimico", subcategoria="Herbicida", unidad="litros")
    assert insumo["subcategoria"] == "herbicida"  # Se normaliza.
    assert insumo["archivado"] is False


def test_campos_numericos_vacios_valen_cero(cliente):
    """Como llega desde el formulario web cuando no completás "Stock mínimo"."""
    insumo = crear(cliente, stock_minimo="", cantidad="")
    assert insumo["stock_minimo"] == 0 and insumo["cantidad"] == 0
    maquina = cliente.post("/maquinas", json={"nombre": "X", "tipo": "otro", "horas_motor": ""})
    assert maquina.status_code == 201 and maquina.json()["horas_motor"] == 0


def test_subcategoria_que_no_corresponde_se_rechaza(cliente):
    r = cliente.post("/insumos", json={"nombre": "X", "categoria": "fertilizante",
                                       "subcategoria": "herbicida", "unidad": "kg"})
    assert r.status_code == 422


def test_no_permite_duplicados_con_tildes(cliente):
    crear(cliente, nombre="Rulemán", categoria="repuesto", unidad="unidades")
    r = cliente.post("/insumos", json={"nombre": "ruleman", "categoria": "repuesto", "unidad": "unidades"})
    assert r.status_code == 409
    assert "Rulemán" in r.json()["detail"]


def test_repuesto_vinculado_a_maquina(cliente):
    maquina = cliente.post("/maquinas", json={"nombre": "JD 6110", "tipo": "tractor"}).json()
    filtro = crear(cliente, nombre="Filtro aceite", categoria="repuesto", subcategoria="filtros",
                   unidad="unidades", maquina_id=maquina["id"])
    assert filtro["maquina_nombre"] == "JD 6110"
    # Un insumo que no es repuesto no guarda máquina.
    urea = crear(cliente, maquina_id=maquina["id"])
    assert urea["maquina_id"] is None


def test_maquina_inexistente(cliente):
    r = cliente.post("/insumos", json={"nombre": "F", "categoria": "repuesto", "unidad": "unidades", "maquina_id": 99})
    assert r.status_code == 400


def test_movimiento_con_coma_y_stock_insuficiente(cliente):
    urea = crear(cliente)
    r = cliente.post(f"/insumos/{urea['id']}/movimientos", json={"tipo": "entrada", "cantidad": "1.500,5"})
    assert r.json()["cantidad"] == 1500.5
    r = cliente.post(f"/insumos/{urea['id']}/movimientos", json={"tipo": "salida", "cantidad": "2000"})
    assert r.status_code == 400
    assert r.json()["detail"] == "No alcanza el stock de Urea: hay 1.500,5 kg"


def test_editar_no_cambia_la_cantidad(cliente):
    urea = crear(cliente, cantidad=10)
    r = cliente.put(f"/insumos/{urea['id']}", json={"nombre": "Urea granulada", "categoria": "fertilizante",
                                                    "subcategoria": "nitrogenado", "unidad": "kg", "stock_minimo": "5"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Urea granulada"
    assert r.json()["cantidad"] == 10


def test_eliminar_sin_movimientos_y_archivar_con_historial(cliente):
    nuevo = crear(cliente, nombre="Sin uso")
    assert cliente.delete(f"/insumos/{nuevo['id']}").status_code == 204

    usado = crear(cliente, nombre="Usado", cantidad=5)
    r = cliente.delete(f"/insumos/{usado['id']}")
    assert r.status_code == 409  # Tiene historial.
    assert cliente.post(f"/insumos/{usado['id']}/archivar").json()["archivado"] is True
    # Archivado: no aparece en la lista normal, sí con incluir_archivados.
    assert all(i["id"] != usado["id"] for i in cliente.get("/insumos").json())
    assert any(i["id"] == usado["id"] for i in cliente.get("/insumos?incluir_archivados=true").json())
    # Y no se le pueden cargar movimientos.
    r = cliente.post(f"/insumos/{usado['id']}/movimientos", json={"tipo": "entrada", "cantidad": 1})
    assert r.status_code == 409


def test_historial_con_filtros(cliente):
    urea = crear(cliente)
    gasoil = crear(cliente, nombre="Gasoil", categoria="combustible", unidad="litros")
    cliente.post(f"/insumos/{urea['id']}/movimientos", json={"tipo": "entrada", "cantidad": 100, "motivo": "compra"})
    cliente.post(f"/insumos/{urea['id']}/movimientos", json={"tipo": "salida", "cantidad": 30, "motivo": "lote 4"})
    cliente.post(f"/insumos/{gasoil['id']}/movimientos", json={"tipo": "entrada", "cantidad": 500})

    assert len(cliente.get("/movimientos").json()) == 3
    assert len(cliente.get("/movimientos?tipo=salida").json()) == 1
    assert len(cliente.get("/movimientos?categoria=combustible").json()) == 1
    assert len(cliente.get("/movimientos?texto=lote").json()) == 1
    assert cliente.get("/movimientos?texto=lote").json()[0]["insumo_nombre"] == "Urea"


def test_texto_con_comillas_no_rompe_el_sql(cliente):
    """Protege contra inyección SQL: el texto se pasa con '?' y no pegado en la consulta."""
    r = cliente.get("/movimientos", params={"texto": "'; DROP TABLE insumos; --"})
    assert r.status_code == 200
    assert cliente.get("/insumos").status_code == 200


def test_alerta_stock_bajo(cliente):
    crear(cliente, stock_minimo=10, cantidad=5)
    alertas = cliente.get("/alertas").json()
    assert [i["nombre"] for i in alertas["stock_bajo"]] == ["Urea"]


def test_opciones(cliente):
    opciones = cliente.get("/opciones").json()
    assert "herbicida" in opciones["subcategorias"]["agroquimico"]
    assert "filtros" in opciones["subcategorias"]["repuesto"]


# ---------- Telegram ----------

def test_nuevo_con_subcategoria_deduce_categoria(bot, cliente):
    respuesta = bot("/nuevo glifosato herbicida litros")
    assert "agroquimico, herbicida" in respuesta
    insumo = cliente.get("/insumos").json()[0]
    assert (insumo["categoria"], insumo["subcategoria"]) == ("agroquimico", "herbicida")


def test_entrada_salida_y_formato_argentino(bot):
    bot("/nuevo urea fertilizante kg")
    assert "Stock actual: 1.500 kg" in bot("/entrada 1.500 urea - compra")
    assert "Stock actual: 1.497,5 kg" in bot("/salida 2,5 urea")
    assert "hay 1.497,5 kg" in bot("/salida 99999 urea")


def test_salida_de_telegram_se_ve_en_la_api(bot, cliente):
    """El 'bug' reportado: lo que se carga por Telegram TIENE que verse en la web."""
    bot("/nuevo urea fertilizante kg")
    bot("/entrada 10 urea")
    bot("/salida 4 urea - lote 2")
    assert cliente.get("/insumos").json()[0]["cantidad"] == 6
    assert cliente.get("/movimientos").json()[0]["motivo"] == "lote 2"


def test_stock_con_filtro(bot):
    bot("/nuevo glifosato herbicida litros")
    bot("/nuevo cipermetrina insecticida litros")
    bot("/nuevo urea fertilizante kg")
    respuesta = bot("/stock herbicidas")
    assert "glifosato" in respuesta and "cipermetrina" not in respuesta and "urea" not in respuesta
    assert "urea" in bot("/stock ure")


def test_repuestos(bot):
    bot("/nuevo filtro aceite filtros unidades")
    bot("/nuevo urea fertilizante kg")
    respuesta = bot("/repuestos")
    assert "filtro aceite" in respuesta and "urea" not in respuesta


def test_archivado_no_aparece_en_telegram(bot, cliente):
    bot("/nuevo urea fertilizante kg")
    insumo = cliente.get("/insumos").json()[0]
    cliente.post(f"/insumos/{insumo['id']}/archivar")
    assert "no existe" in bot("/entrada 5 urea")
    assert "archivado" in bot("/nuevo urea fertilizante kg")


def test_mensajes_largos_se_cortan(bot):
    for n in range(300):
        bot(f"/nuevo insumo numero {n:03d} fertilizante kg")
    assert len(bot("/stock")) <= 4100
