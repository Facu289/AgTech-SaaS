"""El "cartero" de Telegram: trae los mensajes y los manda al backend (POST /mensaje).

No tiene lógica propia: el cerebro del bot está en app/telegram/.
Se arranca desde la carpeta agroapp con:   python bot/bot.py
(El backend tiene que estar corriendo en otra terminal).
"""
import os
import time

import requests
from dotenv import load_dotenv

# Lee el archivo .env y carga sus variables en el entorno.
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
# La API pide login. El bot entra con su propio token (el mismo valor en el .env del backend).
BOT_TOKEN = os.getenv("AGROAPP_BOT_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("Falta TELEGRAM_TOKEN en el archivo .env")
if not BOT_TOKEN:
    raise SystemExit("Falta AGROAPP_BOT_TOKEN en el archivo .env (ver ejemplo_env.txt)")


def leer_usuarios_autorizados():
    """Lee TELEGRAM_USUARIOS_AUTORIZADOS=123,456 del .env y devuelve {123, 456}."""
    valor = os.getenv("TELEGRAM_USUARIOS_AUTORIZADOS", "")
    usuarios = set()
    for parte in valor.split(","):
        parte = parte.strip()
        if not parte:
            continue
        if not parte.isdigit():
            raise SystemExit(f"ID inválido en TELEGRAM_USUARIOS_AUTORIZADOS: '{parte}'")
        usuarios.add(int(parte))
    return usuarios


USUARIOS_AUTORIZADOS = leer_usuarios_autorizados()

# Todas las llamadas a Telegram empiezan con esta dirección.
API_URL = f"https://api.telegram.org/bot{TOKEN}"


def obtener_mensajes(offset):
    """Le pregunta a Telegram si hay mensajes nuevos (espera hasta 30 s)."""
    respuesta = requests.get(
        f"{API_URL}/getUpdates",
        params={"offset": offset, "timeout": 30},
        timeout=35,
    )
    if respuesta.status_code == 401:
        raise SystemExit("Telegram rechazó el token. Revisá TELEGRAM_TOKEN en .env")
    if respuesta.status_code == 409:
        raise SystemExit("Conflicto: ¿tenés el bot abierto en otra terminal?")
    respuesta.raise_for_status()
    return respuesta.json()["result"]


def enviar_mensaje(chat_id, texto):
    """Envía un mensaje de texto a un chat."""
    respuesta = requests.post(
        f"{API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": texto},
        timeout=10,
    )
    respuesta.raise_for_status()


def pedir_respuesta_al_backend(texto, usuario_id):
    """Le manda el texto a nuestra API FastAPI y devuelve lo que contesta.

    Mandamos también quién escribe: si el mensaje es en lenguaje natural,
    el backend guarda lo que entendió hasta que ESE usuario responda "sí".
    """
    try:
        respuesta = requests.post(
            f"{BACKEND_URL}/mensaje",
            json={"texto": texto, "usuario": usuario_id},
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
            timeout=45,  # Gemini puede tardar unos segundos en contestar.
        )
        if respuesta.status_code == 401:
            print("El backend rechazó el token del bot: revisá AGROAPP_BOT_TOKEN en el .env.")
            return "⚠️ El bot no pudo entrar a AgroApp (token del bot incorrecto)."
        respuesta.raise_for_status()
        return respuesta.json()["respuesta"]
    except requests.RequestException as error:
        print(f"No pude hablar con el backend ({type(error).__name__}).")
        return "⚠️ El servidor de AgroApp no está disponible. Probá en un rato."


def main():
    print(f"Bot iniciado. Backend: {BACKEND_URL}. Esperando mensajes... (Ctrl+C para detener)")
    if not USUARIOS_AUTORIZADOS:
        print("⚠️ No hay usuarios autorizados: el bot va a rechazar a todos.")

    offset = None

    while True:
        try:
            mensajes = obtener_mensajes(offset)

            for update in mensajes:
                # Avisamos a Telegram que este mensaje ya lo procesamos.
                offset = update["update_id"] + 1

                mensaje = update.get("message")
                if not mensaje or "text" not in mensaje or "from" not in mensaje:
                    continue  # Ignoramos fotos, stickers, etc. por ahora.

                chat_id = mensaje["chat"]["id"]
                usuario_id = mensaje["from"]["id"]
                texto = mensaje["text"]

                # Seguridad: solo los usuarios autorizados llegan al backend.
                if usuario_id not in USUARIOS_AUTORIZADOS:
                    print(f"⛔ Rechazado usuario {usuario_id}: {texto}")
                    enviar_mensaje(chat_id, f"⛔ No estás autorizado. Tu ID de usuario es {usuario_id}.")
                    continue

                print(f"Mensaje de {usuario_id}: {texto}")
                respuesta = pedir_respuesta_al_backend(texto, usuario_id)
                enviar_mensaje(chat_id, respuesta)

        except requests.RequestException as error:
            # Mostramos solo el tipo de error para no imprimir el token.
            print(f"Error de conexión con Telegram ({type(error).__name__}). Reintento en 5 s...")
            time.sleep(5)


if __name__ == "__main__":
    main()