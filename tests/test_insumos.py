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


def test_repuesto_para_varias_maquinas(cliente):
    jd = cliente.post("/maquinas", json={"nombre": "JD 6110", "tipo": "tractor"}).json()
    axial = cliente.post("/maquinas", json={"nombre": "Axial 8250", "tipo": "cosechadora"}).json()
    filtro = crear(cliente, nombre="Filtro aceite", categoria="repuesto", subcategoria="filtros",
                   unidad="unidades", maquinas=[jd["id"], axial["id"], jd["id"]])  # jd repetida a propósito.
    assert [m["nombre"] for m in filtro["maquinas"]] == ["Axial 8250", "JD 6110"]  # Sin repetidos, por nombre.
    # Aparece en la ficha de AMBAS máquinas.
    for maquina in (jd, axial):
        repuestos = cliente.get(f"/maquinas/{maquina['id']}").json()["repuestos"]
        assert [r["nombre"] for r in repuestos] == ["Filtro aceite"]
    # Un insumo que no es repuesto no guarda máquinas.
    urea = crear(cliente, maquinas=[jd["id"]])
    assert urea["maquinas"] == []


def test_editar_cambia_las_maquinas(cliente):
    jd = cliente.post("/maquinas", json={"nombre": "JD", "tipo": "tractor"}).json()
    axial = cliente.post("/maquinas", json={"nombre": "Axial", "tipo": "cosechadora"}).json()
    correa = crear(cliente, nombre="Correa", categoria="repuesto", unidad="unidades", maquinas=[jd["id"]])
    datos = {"nombre": "Correa", "categoria": "repuesto", "unidad": "unidades"}
    r = cliente.put(f"/insumos/{correa['id']}", json={**datos, "maquinas": [axial["id"]]})
    assert [m["nombre"] for m in r.json()["maquinas"]] == ["Axial"]
    assert cliente.get(f"/maquinas/{jd['id']}").json()["repuestos"] == []
    r = cliente.put(f"/insumos/{correa['id']}", json={**datos, "maquinas": []})  # General.
    assert r.json()["maquinas"] == []


def test_todavia_acepta_maquina_id(cliente):
    """Compatibilidad con la forma vieja (una sola máquina)."""
    jd = cliente.post("/maquinas", json={"nombre": "JD", "tipo": "tractor"}).json()
    rep = crear(cliente, nombre="Bujía", categoria="repuesto", unidad="unidades", maquina_id=jd["id"])
    assert [m["id"] for m in rep["maquinas"]] == [jd["id"]]
    general = crear(cliente, nombre="Grasa", categoria="repuesto", unidad="kg", maquina_id="")
    assert general["maquinas"] == []


def test_maquina_con_repuestos_no_se_borra_y_repuesto_se_borra(cliente):
    jd = cliente.post("/maquinas", json={"nombre": "JD", "tipo": "tractor"}).json()
    rep = crear(cliente, nombre="Bujía", categoria="repuesto", unidad="unidades", maquinas=[jd["id"]])
    assert cliente.delete(f"/maquinas/{jd['id']}").status_code == 409  # Tiene repuestos vinculados.
    assert cliente.delete(f"/insumos/{rep['id']}").status_code == 204  # El repuesto sí (sin movimientos).
    assert cliente.delete(f"/maquinas/{jd['id']}").status_code == 204  # Ahora la máquina queda libre.


def test_maquina_inexistente(cliente):
    r = cliente.post("/insumos", json={"nombre": "F", "categoria": "repuesto", "unidad": "unidades", "maquinas": [99]})
    assert r.status_code == 400 and "99" in r.json()["detail"]


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
    assert opciones["hojas_insumos"]["quimicos"] == ["agroquimico"]
    assert opciones["hojas_insumos"]["repuestos"] == ["repuesto"]
    assert "fertilizante" in opciones["hojas_insumos"]["insumos"]


def test_cada_insumo_dice_su_hoja(cliente):
    """La web separa Insumos, Químicos y Repuestos con el campo "hoja" (sale de la categoría)."""
    crear(cliente)  # Urea, fertilizante.
    crear(cliente, nombre="Glifosato", categoria="agroquimico", unidad="litros")
    crear(cliente, nombre="Filtro", categoria="repuesto", unidad="unidades")
    hojas = {i["nombre"]: i["hoja"] for i in cliente.get("/insumos").json()}
    assert hojas == {"Urea": "insumos", "Glifosato": "quimicos", "Filtro": "repuestos"}
    # Si se le cambia la categoría, cambia de hoja (no hay nada más que tocar en la base).
    glifo = next(i for i in cliente.get("/insumos").json() if i["nombre"] == "Glifosato")
    editado = cliente.put(f"/insumos/{glifo['id']}", json={"nombre": "Glifosato", "categoria": "otro", "unidad": "litros"})
    assert editado.json()["hoja"] == "insumos"


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


def test_quimicos(bot):
    assert "No hay químicos" in bot("/quimicos")
    bot("/nuevo glifosato herbicida litros")
    bot("/nuevo cipermetrina insecticida litros")
    bot("/nuevo urea fertilizante kg")
    bot("/nuevo filtro aceite filtros unidades")
    respuesta = bot("/quimicos")
    assert "glifosato" in respuesta and "cipermetrina" in respuesta
    assert "urea" not in respuesta and "filtro" not in respuesta
    assert "cipermetrina" not in bot("/quimicos herbicida")
    assert "No encontré químicos" in bot("/quimicos urea")
    assert "glifosato" in bot("/químicos")  # Con tilde también.


def test_repuestos(bot, cliente):
    bot("/nuevo filtro aceite filtros unidades")
    bot("/nuevo urea fertilizante kg")
    respuesta = bot("/repuestos")
    assert "filtro aceite" in respuesta and "urea" not in respuesta
    # Con varias máquinas: se listan todas y se puede filtrar por cualquiera.
    jd = cliente.post("/maquinas", json={"nombre": "Tractor JD", "tipo": "tractor"}).json()
    axial = cliente.post("/maquinas", json={"nombre": "Cosechadora Axial", "tipo": "cosechadora"}).json()
    filtro = next(i for i in cliente.get("/insumos").json() if i["nombre"] == "filtro aceite")
    cliente.put(f"/insumos/{filtro['id']}", json={"nombre": "filtro aceite", "categoria": "repuesto",
                                                 "unidad": "unidades", "maquinas": [jd["id"], axial["id"]]})
    assert "→ Cosechadora Axial, Tractor JD" in bot("/repuestos")
    assert "filtro aceite" in bot("/repuestos axial") and "filtro aceite" in bot("/repuestos jd")


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
