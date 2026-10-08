"""Tests del bot de WhatsApp. Meta se SIMULA: ningún test manda nada de verdad."""
import hashlib
import hmac
import json
import sys

import pytest

SECRETO = "secreto-de-prueba"
MI_NUMERO = "5493511234567"  # Así lo manda WhatsApp (Argentina: 54 + 9 + característica + número).


@pytest.fixture
def whatsapp(app, monkeypatch):
    """Configura WhatsApp con datos de prueba y reemplaza el envío a Meta por una lista."""
    modulo = sys.modules["app.whatsapp.rutas"]
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRETO)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "token-verificacion")
    monkeypatch.setenv("WHATSAPP_TOKEN", "token-meta")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1390060194181902")
    # Escrito "a mano", con espacios y guiones: tiene que reconocerlo igual.
    monkeypatch.setenv("WHATSAPP_USUARIOS_AUTORIZADOS", "+54 9 351 123-4567, 5491100000000")
    enviados = []
    monkeypatch.setattr(modulo, "enviar_texto", lambda numero, texto: enviados.append((numero, texto)))
    modulo._mensajes_vistos.clear()
    return enviados


def aviso(texto="/ayuda", numero=MI_NUMERO, id_mensaje="wamid.1", tipo="text"):
    """Arma un aviso como los que manda Meta."""
    mensaje = {"from": numero, "id": id_mensaje, "timestamp": "1700000000", "type": tipo}
    if tipo == "text":
        mensaje["text"] = {"body": texto}
    valor = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550000000", "phone_number_id": "1390060194181902"},
        "contacts": [{"profile": {"name": "Facu"}, "wa_id": numero}],
        "messages": [mensaje],
    }
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "2291926221567276", "changes": [{"value": valor, "field": "messages"}]}]}


def firmar(cuerpo: bytes, secreto=SECRETO):
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def mandar(cliente, datos, firma=None):
    cuerpo = json.dumps(datos).encode()
    encabezados = {"Content-Type": "application/json"}
    encabezados["X-Hub-Signature-256"] = firma if firma is not None else firmar(cuerpo)
    return cliente.post("/whatsapp", content=cuerpo, headers=encabezados)


# ---------- Verificación del webhook (GET) ----------

def test_verificacion_con_token_correcto_devuelve_el_challenge(cliente_anonimo, whatsapp):
    respuesta = cliente_anonimo.get("/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "token-verificacion", "hub.challenge": "12345"})
    assert respuesta.status_code == 200
    assert respuesta.text == "12345"


def test_verificacion_con_token_incorrecto_se_rechaza(cliente_anonimo, whatsapp):
    respuesta = cliente_anonimo.get("/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "12345"})
    assert respuesta.status_code == 403


def test_sin_verify_token_configurado_no_verifica_nada(cliente_anonimo, whatsapp, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "")
    respuesta = cliente_anonimo.get("/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "12345"})
    assert respuesta.status_code == 403


# ---------- Firma (POST) ----------

def test_mensaje_con_firma_valida_se_contesta(cliente_anonimo, whatsapp):
    """Sin login (cliente_anonimo): /whatsapp no pide cookie, la seguridad es la firma."""
    respuesta = mandar(cliente_anonimo, aviso("/ayuda"))
    assert respuesta.status_code == 200
    assert len(whatsapp) == 1
    numero, texto = whatsapp[0]
    assert numero == MI_NUMERO
    assert "Comandos de AgroApp" in texto


@pytest.mark.parametrize("firma", ["", "sha256=000", "md5=abc", firmar(b"otro cuerpo")])
def test_mensaje_con_firma_invalida_se_rechaza(cliente_anonimo, whatsapp, firma):
    respuesta = mandar(cliente_anonimo, aviso("/ayuda"), firma=firma)
    assert respuesta.status_code == 403
    assert whatsapp == []


def test_firma_hecha_con_otro_secreto_se_rechaza(cliente_anonimo, whatsapp):
    cuerpo = json.dumps(aviso("/ayuda")).encode()
    respuesta = mandar(cliente_anonimo, aviso("/ayuda"), firma=firmar(cuerpo, "secreto-falso"))
    assert respuesta.status_code == 403


def test_sin_app_secret_configurado_rechaza_todo(cliente_anonimo, whatsapp, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "")
    respuesta = mandar(cliente_anonimo, aviso("/ayuda"), firma=firmar(json.dumps(aviso("/ayuda")).encode(), ""))
    assert respuesta.status_code == 403
    assert whatsapp == []


def test_el_login_sigue_protegiendo_lo_demas(cliente_anonimo, whatsapp):
    """Liberar /whatsapp no tiene que liberar otras rutas."""
    assert cliente_anonimo.get("/insumos").status_code == 401
    assert cliente_anonimo.get("/whatsapp/../insumos").status_code == 401


# ---------- Quién puede usarlo ----------

def test_numero_no_autorizado_no_llega_a_la_app(cliente_anonimo, whatsapp, monkeypatch):
    llamado = []
    monkeypatch.setattr(sys.modules["app.whatsapp.rutas"], "generar_respuesta", lambda *a: llamado.append(a))
    respuesta = mandar(cliente_anonimo, aviso("/stock", numero="5491199999999"))
    assert respuesta.status_code == 200  # A Meta siempre le decimos "recibido".
    assert llamado == []
    assert whatsapp == [("5491199999999", "⛔ No estás autorizado. Tu número es 5491199999999.")]


@pytest.mark.parametrize("escrito", [
    "5493511234567", "+54 9 351 123-4567", "543511234567", "3511234567", "0054 9 351 1234567",
])
def test_normalizar_numero_argentino(app, escrito):
    normalizar = sys.modules["app.whatsapp.rutas"].normalizar_numero
    assert normalizar(escrito) == normalizar("5493511234567") == "543511234567"


def test_numeros_distintos_no_se_confunden(app):
    normalizar = sys.modules["app.whatsapp.rutas"].normalizar_numero
    assert normalizar("5493511234567") != normalizar("5493511234568")


# ---------- Qué contesta ----------

def test_ignora_los_estados(cliente_anonimo, whatsapp):
    """Meta también avisa "enviado / entregado / leído": eso no se contesta."""
    datos = aviso()
    valor = datos["entry"][0]["changes"][0]["value"]
    del valor["messages"]
    valor["statuses"] = [{"id": "wamid.x", "status": "delivered", "recipient_id": MI_NUMERO}]
    assert mandar(cliente_anonimo, datos).status_code == 200
    assert whatsapp == []


def test_mensaje_que_no_es_texto_responde_amable(cliente_anonimo, whatsapp):
    assert mandar(cliente_anonimo, aviso(tipo="image")).status_code == 200
    assert len(whatsapp) == 1
    assert "solo entiendo mensajes de texto" in whatsapp[0][1]


def test_el_mismo_mensaje_repetido_se_atiende_una_vez(cliente_anonimo, whatsapp):
    mandar(cliente_anonimo, aviso("/ayuda", id_mensaje="wamid.repetido"))
    mandar(cliente_anonimo, aviso("/ayuda", id_mensaje="wamid.repetido"))
    assert len(whatsapp) == 1


def test_comandos_usan_la_misma_logica_que_telegram(cliente, whatsapp):
    mandar(cliente, aviso("/nuevo glifosato herbicida litros", id_mensaje="a"))
    mandar(cliente, aviso("/entrada 20 glifosato - compra", id_mensaje="b"))
    assert cliente.get("/insumos").json()[0]["cantidad"] == 20
    assert "Stock actual: 20 litros" in whatsapp[-1][1]


def test_lenguaje_natural_pide_si_y_guarda_el_pendiente_por_numero(cliente, whatsapp, monkeypatch):
    from app.telegram import lenguaje_natural
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(lenguaje_natural, "consultar_gemini",
                        lambda instrucciones, mensaje: '{"comandos": ["/entrada 5 urea"], "pregunta": ""}')
    mandar(cliente, aviso("/nuevo urea fertilizante kg", id_mensaje="1"))
    mandar(cliente, aviso("compré 5 kilos de urea", id_mensaje="2"))
    assert "Entendí esto" in whatsapp[-1][1]
    assert cliente.get("/insumos").json()[0]["cantidad"] == 0  # Todavía no.

    # Otro número autorizado dice "sí": no es SU pendiente.
    mandar(cliente, aviso("sí", numero="5491100000000", id_mensaje="3"))
    assert "No tengo nada pendiente" in whatsapp[-1][1]

    # El mismo número dice "sí": se registra.
    mandar(cliente, aviso("sí", id_mensaje="4"))
    assert cliente.get("/insumos").json()[0]["cantidad"] == 5


# ---------- Mandar a Meta (Graph API) ----------

class RespuestaFalsa:
    def __init__(self, codigo, datos):
        self.status_code = codigo
        self.ok = codigo < 400
        self._datos = datos
        self.text = json.dumps(datos)

    def json(self):
        return self._datos


@pytest.fixture
def meta(app, monkeypatch):
    """Reemplaza requests.post de app/whatsapp/rutas.py: guarda lo pedido y devuelve lo que digamos."""
    modulo = sys.modules["app.whatsapp.rutas"]
    monkeypatch.setenv("WHATSAPP_TOKEN", "token-meta")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1390060194181902")
    monkeypatch.delenv("WHATSAPP_GRAPH_VERSION", raising=False)
    estado = {"pedidos": [], "respuestas": []}

    def post(url, headers, json, timeout):
        estado["pedidos"].append({"url": url, "headers": headers, "json": json})
        return estado["respuestas"].pop(0) if estado["respuestas"] else RespuestaFalsa(200, {"messages": [{"id": "x"}]})

    monkeypatch.setattr(modulo.requests, "post", post)
    return estado


def test_enviar_texto_arma_bien_el_pedido(app, meta):
    sys.modules["app.whatsapp.rutas"].enviar_texto(MI_NUMERO, "hola")
    pedido = meta["pedidos"][0]
    assert pedido["url"] == "https://graph.facebook.com/v26.0/1390060194181902/messages"
    assert pedido["headers"]["Authorization"] == "Bearer token-meta"
    assert pedido["json"] == {"messaging_product": "whatsapp", "to": MI_NUMERO,
                              "type": "text", "text": {"body": "hola"}}


def test_si_meta_rechaza_el_numero_con_9_reintenta_sin_9(app, meta):
    meta["respuestas"] = [RespuestaFalsa(400, {"error": {"code": 131030, "message": "not in allowed list"}})]
    sys.modules["app.whatsapp.rutas"].enviar_texto(MI_NUMERO, "hola")
    assert [p["json"]["to"] for p in meta["pedidos"]] == [MI_NUMERO, "543511234567"]


def test_otro_error_de_meta_se_informa(app, meta):
    modulo = sys.modules["app.whatsapp.rutas"]
    meta["respuestas"] = [RespuestaFalsa(401, {"error": {"code": 190, "message": "token vencido"}})]
    with pytest.raises(modulo.ErrorWhatsApp, match="401"):
        modulo.enviar_texto(MI_NUMERO, "hola")
    assert len(meta["pedidos"]) == 1  # No reintenta: no es un problema del número.


def test_si_meta_falla_el_webhook_igual_responde_200(cliente_anonimo, meta, monkeypatch):
    """Si no podemos contestar, Meta igual tiene que recibir 200 (si no, reintenta sin parar).

    Acá NO usamos el fixture "whatsapp": queremos el enviar_texto real, con Meta "caído".
    """
    monkeypatch.setenv("WHATSAPP_APP_SECRET", SECRETO)
    monkeypatch.setenv("WHATSAPP_USUARIOS_AUTORIZADOS", MI_NUMERO)
    meta["respuestas"] = [RespuestaFalsa(500, {"error": {"code": 1}})]
    assert mandar(cliente_anonimo, aviso("/ayuda", id_mensaje="caido")).status_code == 200
    assert len(meta["pedidos"]) == 1  # Intentó contestar (y falló sin romper nada).
