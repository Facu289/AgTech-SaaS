"""El "cartero" de WhatsApp (Meta WhatsApp Cloud API).

A diferencia de Telegram (donde bot/bot.py PREGUNTA cada tanto si hay mensajes), acá
Meta nos AVISA: cada mensaje llega como un pedido POST a /whatsapp (eso es un "webhook").
Por eso el cartero vive dentro del backend y no en un programa aparte.

Cómo funciona:
1. Al configurar el webhook en Meta, Meta hace un GET /whatsapp con un código (hub.challenge)
   y nuestro token de verificación. Si el token coincide, devolvemos el código: "sí, soy yo".
2. Cada mensaje llega por POST /whatsapp, FIRMADO por Meta con el App Secret
   (encabezado X-Hub-Signature-256). Si la firma no coincide, lo rechazamos: así nadie
   puede hacerse pasar por Meta. Esta ruta no pide login: la seguridad es la firma.
3. Contestamos 200 enseguida (si Meta no recibe respuesta rápido, reintenta) y el mensaje
   se atiende "de fondo": se revisa que el número esté autorizado, se pasa por la MISMA
   lógica que Telegram (generar_respuesta: comandos, Gemini y el "sí") y se contesta por
   la Graph API de Meta.

Configuración en el archivo .env (ver ejemplo_env.txt):
    WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_SECRET,
    WHATSAPP_VERIFY_TOKEN, WHATSAPP_USUARIOS_AUTORIZADOS, WHATSAPP_GRAPH_VERSION (opcional)
"""
import hashlib
import hmac
import json
import os
from collections import deque

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.telegram.comandos import generar_respuesta

router = APIRouter(tags=["WhatsApp"])

# Versión de la Graph API de Meta. Meta saca una nueva cada pocos meses y cada una dura
# unos dos años. Si en el futuro deja de andar, se cambia en el .env sin tocar el código.
VERSION_GRAPH_POR_DEFECTO = "v26.0"
URL_GRAPH = "https://graph.facebook.com/{version}/{phone_number_id}/messages"

# Código de error de Meta: "el número destino no está en la lista permitida" (cuenta de prueba).
ERROR_NUMERO_NO_PERMITIDO = 131030

# Meta puede mandar el MISMO mensaje dos veces (si cree que no lo recibimos).
# Guardamos los ids de los últimos mensajes para no registrar algo dos veces.
_mensajes_vistos = deque(maxlen=500)


# ---------- Números de teléfono ----------

def normalizar_numero(numero: str) -> str:
    """Deja un número en una forma única para poder compararlo.

    WhatsApp manda los números de Argentina como 549 + característica + número
    (ej: 5493511234567), pero en la lista uno puede escribir "+54 9 351 123-4567",
    "54 351 1234567" o "3511234567". Todos quedan como 543511234567:
    solo dígitos, con el 54 adelante y sin el 9 de celular.
    """
    digitos = "".join(c for c in str(numero) if c.isdigit())
    if digitos.startswith("00"):          # 0054... (formato internacional con 00)
        digitos = digitos[2:]
    if digitos.startswith("549"):
        digitos = "54" + digitos[3:]
    elif len(digitos) == 10:              # Número argentino sin el 54 (351 1234567).
        digitos = "54" + digitos
    return digitos


def leer_autorizados() -> set:
    """Lee WHATSAPP_USUARIOS_AUTORIZADOS=5493511234567,5493517654321 del .env."""
    valor = os.getenv("WHATSAPP_USUARIOS_AUTORIZADOS", "")
    return {normalizar_numero(parte) for parte in valor.split(",") if normalizar_numero(parte)}


def esta_autorizado(numero: str) -> bool:
    return normalizar_numero(numero) in leer_autorizados()


# ---------- Firma de Meta ----------

def firma_valida(cuerpo: bytes, encabezado: str) -> bool:
    """¿El mensaje lo mandó Meta de verdad?

    Meta calcula un HMAC-SHA256 del cuerpo EXACTO del pedido usando el App Secret
    (que solo saben Meta y nosotros) y lo manda como "sha256=<huella>". Nosotros calculamos
    lo mismo: si las huellas coinciden, el mensaje es de Meta y nadie lo cambió en el camino.
    """
    secreto = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not secreto or not encabezado or not encabezado.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    # compare_digest tarda lo mismo aunque difieran al principio o al final:
    # así no se puede adivinar la huella "midiendo cuánto tarda".
    return hmac.compare_digest(esperada, encabezado.removeprefix("sha256=").strip())


# ---------- Mandar mensajes (Graph API) ----------

class ErrorWhatsApp(Exception):
    """Meta no aceptó el mensaje que quisimos mandar."""


def _post_a_meta(numero: str, texto: str) -> requests.Response:
    url = URL_GRAPH.format(
        version=os.getenv("WHATSAPP_GRAPH_VERSION", VERSION_GRAPH_POR_DEFECTO).strip(),
        phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
    )
    return requests.post(
        url,
        headers={"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN', '').strip()}"},
        json={
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto},
        },
        timeout=15,
    )


def _codigo_error(respuesta: requests.Response):
    try:
        return respuesta.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None


def enviar_texto(numero: str, texto: str):
    """Manda un mensaje de texto por WhatsApp al número indicado (como lo mandó Meta: 549...).

    Particularidad de Argentina: a veces Meta rechaza el número con el 9 (sobre todo con la
    cuenta de prueba, error 131030). En ese caso reintentamos una vez sin el 9.
    """
    respuesta = _post_a_meta(numero, texto)
    if (not respuesta.ok and _codigo_error(respuesta) == ERROR_NUMERO_NO_PERMITIDO
            and numero.startswith("549")):
        respuesta = _post_a_meta("54" + numero[3:], texto)
    if not respuesta.ok:
        # Solo el código y un pedazo del error (nunca el token).
        raise ErrorWhatsApp(f"Meta respondió {respuesta.status_code}: {respuesta.text[:300]}")


# ---------- Atender un mensaje ----------

def atender_mensaje(mensaje: dict):
    """Responde UN mensaje entrante. Corre de fondo, después de contestarle 200 a Meta."""
    numero = mensaje.get("from", "")
    if not numero:
        return
    id_mensaje = mensaje.get("id")
    if id_mensaje:
        if id_mensaje in _mensajes_vistos:
            return  # Meta lo mandó dos veces: ya lo atendimos.
        _mensajes_vistos.append(id_mensaje)

    if not esta_autorizado(numero):
        print(f"⛔ WhatsApp: rechazado el número {numero}")
        respuesta = f"⛔ No estás autorizado. Tu número es {numero}."
    elif mensaje.get("type") != "text":
        respuesta = "🙂 Por ahora solo entiendo mensajes de texto. Escribí /ayuda para ver qué sé hacer."
    else:
        texto = mensaje.get("text", {}).get("body", "")
        print(f"WhatsApp: mensaje de {numero}")
        # "whatsapp:..." para que lo pendiente de confirmar ("sí") no se mezcle con Telegram.
        respuesta = generar_respuesta(texto, f"whatsapp:{normalizar_numero(numero)}")

    try:
        enviar_texto(numero, respuesta)
    except (ErrorWhatsApp, requests.RequestException) as error:
        print(f"No pude contestar por WhatsApp ({type(error).__name__}): {error}")


def mensajes_entrantes(datos: dict) -> list:
    """Saca los mensajes del aviso de Meta. Ignora los "estados" (enviado, entregado, leído)."""
    mensajes = []
    for entrada in datos.get("entry", []) or []:
        for cambio in entrada.get("changes", []) or []:
            valor = cambio.get("value", {}) or {}
            mensajes += valor.get("messages", []) or []
    return mensajes


# ---------- Endpoints ----------

@router.get("/whatsapp", response_class=PlainTextResponse)
def verificar_webhook(request: Request):
    """Meta lo llama UNA vez al configurar el webhook, para comprobar que somos nosotros."""
    parametros = request.query_params
    esperado = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    recibido = parametros.get("hub.verify_token", "")
    if (parametros.get("hub.mode") == "subscribe" and esperado
            and hmac.compare_digest(recibido.encode(), esperado.encode())):
        return parametros.get("hub.challenge", "")
    raise HTTPException(403, "Token de verificación incorrecto.")


@router.post("/whatsapp")
async def recibir_webhook(request: Request, tareas: BackgroundTasks):
    """Meta manda acá cada mensaje (y cada cambio de estado de los que mandamos)."""
    # La firma se calcula sobre el cuerpo CRUDO (los bytes tal cual llegaron),
    # por eso lo leemos así y no dejamos que FastAPI lo convierta antes.
    cuerpo = await request.body()
    if not firma_valida(cuerpo, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Firma inválida.")
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        raise HTTPException(400, "El cuerpo no es JSON.")

    for mensaje in mensajes_entrantes(datos):
        tareas.add_task(atender_mensaje, mensaje)  # Se atiende después de contestar.
    return {"recibido": True}
