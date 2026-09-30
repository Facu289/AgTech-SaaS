"""Tests de la carga en lenguaje natural. Gemini se SIMULA: no se usa internet."""
import json

import pytest


@pytest.fixture
def gemini(app, monkeypatch):
    """Reemplaza a Gemini por una función que devuelve lo que le digamos."""
    import lenguaje_natural
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    estado = {"respuesta": {"comandos": [], "pregunta": ""}, "mensajes": []}

    def falso(instrucciones, mensaje):
        estado["mensajes"].append(mensaje)
        estado["instrucciones"] = instrucciones
        return "```json\n" + json.dumps(estado["respuesta"]) + "\n```"  # Como a veces responde Gemini.

    monkeypatch.setattr(lenguaje_natural, "consultar_gemini", falso)
    return estado


def responder(gemini, *comandos, pregunta=""):
    gemini["respuesta"] = {"comandos": list(comandos), "pregunta": pregunta}


def test_escritura_pide_confirmacion_y_si_la_registra(app, bot, gemini, cliente):
    bot("/nuevo glifosato herbicida litros")
    responder(gemini, "/entrada 20 glifosato - compra")
    respuesta = bot("compré 20 litros de glifosato", 111)
    assert "Entendí esto" in respuesta and "/entrada 20 glifosato - compra" in respuesta
    assert cliente.get("/insumos").json()[0]["cantidad"] == 0  # Todavía NO se registró.
    assert "Stock actual: 20 litros" in bot("Sí!", 111)
    assert cliente.get("/insumos").json()[0]["cantidad"] == 20
    assert "No tengo nada pendiente" in bot("si", 111)  # Ya se usó.


def test_no_cancela(bot, gemini, cliente):
    bot("/nuevo urea fertilizante kg")
    responder(gemini, "/entrada 5 urea")
    bot("entraron 5 kg de urea", 7)
    assert "Cancelado" in bot("no", 7)
    assert cliente.get("/insumos").json()[0]["cantidad"] == 0


def test_la_confirmacion_es_de_cada_usuario(bot, gemini, cliente):
    bot("/nuevo urea fertilizante kg")
    responder(gemini, "/entrada 5 urea")
    bot("entraron 5 kg de urea", 1)
    assert "No tengo nada pendiente" in bot("sí", 2)  # Otro usuario no puede confirmar.
    assert "Stock actual" in bot("/si", 1)


def test_consultas_se_responden_directo(bot, gemini):
    bot("/nuevo glifosato herbicida litros")
    responder(gemini, "/stock herbicida")
    respuesta = bot("¿cuánto herbicida me queda?", 5)
    assert "glifosato" in respuesta and "Entendí" not in respuesta


def test_varios_comandos_juntos(bot, gemini, cliente):
    bot("/nuevo glifosato herbicida litros")
    bot("/nuevo urea fertilizante kg")
    responder(gemini, "/entrada 10 glifosato", "/entrada 3 urea")
    bot("llegaron 10 de glifo y 3 de urea", 9)
    respuesta = bot("dale", 9)
    assert respuesta.count("Entrada registrada") == 2


def test_pregunta_si_falta_un_dato(bot, gemini):
    responder(gemini, pregunta="¿Cuántos litros de glifosato usaste?")
    assert bot("usé glifosato", 3) == "🤖 ¿Cuántos litros de glifosato usaste?"


def test_comandos_peligrosos_o_inventados_se_descartan(bot, gemini):
    """Seguridad: aunque la IA devuelva algo raro, solo pasan comandos conocidos."""
    responder(gemini, "/borrar_todo", "DROP TABLE insumos", "/stock\n/salida 99 urea")
    assert "No entendí" in bot("hacé cualquier cosa", 4)


def test_instrucciones_incluyen_los_nombres_cargados(bot, gemini):
    bot("/nuevo glifosato herbicida litros")
    responder(gemini, "/stock")
    bot("stock", 1)
    assert "glifosato" in gemini["instrucciones"]


def test_sin_clave_explica_como_configurarla(bot, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert "GEMINI_API_KEY" in bot("gasté 20 de glifosato", 1)


def test_los_comandos_con_barra_no_usan_gemini(bot, gemini):
    bot("/stock")
    assert gemini["mensajes"] == []


def test_la_api_recibe_el_usuario(cliente, gemini):
    cliente.post("/mensaje", json={"texto": "/nuevo urea fertilizante kg"})
    responder(gemini, "/entrada 5 urea")
    cliente.post("/mensaje", json={"texto": "entraron 5 de urea", "usuario": 42})
    r = cliente.post("/mensaje", json={"texto": "sí", "usuario": 42})
    assert "Stock actual: 5 kg" in r.json()["respuesta"]


def test_leer_respuesta_tolera_texto_alrededor():
    from lenguaje_natural import ErrorGemini, leer_respuesta
    assert leer_respuesta('Claro: {"comandos": ["/stock"], "pregunta": ""} listo')["comandos"] == ["/stock"]
    with pytest.raises(ErrorGemini):
        leer_respuesta("no sé")


class RespuestaFalsa:
    def __init__(self, codigo, datos=None):
        self.status_code, self._datos, self.text = codigo, datos, json.dumps(datos)
        self.ok = codigo < 400

    def json(self):
        return self._datos


@pytest.mark.parametrize("codigo, esperado", [
    (429, "límite"), (404, "modelo"), (403, "clave"), (500, "error"),
])
def test_errores_de_gemini_se_explican(app, monkeypatch, codigo, esperado):
    import lenguaje_natural
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(lenguaje_natural.requests, "post", lambda *a, **k: RespuestaFalsa(codigo, {}))
    with pytest.raises(lenguaje_natural.ErrorGemini, match=esperado):
        lenguaje_natural.consultar_gemini("instrucciones", "hola")


def test_consultar_gemini_arma_bien_el_pedido(app, monkeypatch):
    import lenguaje_natural
    monkeypatch.setenv("GEMINI_API_KEY", "mi-clave")
    monkeypatch.setenv("GEMINI_MODEL", "modelo-x")
    pedido = {}

    def post(url, headers, json, timeout):
        pedido.update(url=url, headers=headers, cuerpo=json)
        return RespuestaFalsa(200, {"candidates": [{"content": {"parts": [{"text": '{"comandos": []}'}]}}]})

    monkeypatch.setattr(lenguaje_natural.requests, "post", post)
    assert lenguaje_natural.consultar_gemini("reglas", "hola") == '{"comandos": []}'
    assert pedido["url"].endswith("/models/modelo-x:generateContent")
    assert pedido["headers"]["x-goog-api-key"] == "mi-clave"
    assert "hola" in pedido["cuerpo"]["contents"][0]["parts"][0]["text"]


def test_sin_internet(app, monkeypatch):
    import lenguaje_natural
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def falla(*a, **k):
        raise lenguaje_natural.requests.ConnectionError()

    monkeypatch.setattr(lenguaje_natural.requests, "post", falla)
    with pytest.raises(lenguaje_natural.ErrorGemini, match="internet"):
        lenguaje_natural.consultar_gemini("i", "m")
