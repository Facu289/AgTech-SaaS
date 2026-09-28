import os
import time

import requests
from dotenv import load_dotenv

# Lee el archivo .env y carga sus variables en el entorno.
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

if not TOKEN:
    raise SystemExit("Falta TELEGRAM_TOKEN en el archivo .env")

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


def pedir_respuesta_al_backend(texto):
    """Le manda el texto a nuestra API FastAPI y devuelve lo que contesta."""
    try:
        respuesta = requests.post(
            f"{BACKEND_URL}/mensaje",
            json={"texto": texto},
            timeout=10,
        )
        respuesta.raise_for_status()
        return respuesta.json()["respuesta"]
    except requests.RequestException as error:
        print(f"No pude hablar con el backend ({type(error).__name__}).")
        return "⚠️ El servidor de AgroApp no está disponible. Probá en un rato."


def main():
    print(f"Bot iniciado. Backend: {BACKEND_URL}. Esperando mensajes... (Ctrl+C para detener)")
    offset = None

    while True:
        try:
            mensajes = obtener_mensajes(offset)

            for update in mensajes:
                # Avisamos a Telegram que este mensaje ya lo procesamos.
                offset = update["update_id"] + 1

                mensaje = update.get("message")
                if not mensaje or "text" not in mensaje:
                    continue  # Ignoramos fotos, stickers, etc. por ahora.

                chat_id = mensaje["chat"]["id"]
                texto = mensaje["text"]
                print(f"Mensaje recibido de {chat_id}: {texto}")

                respuesta = pedir_respuesta_al_backend(texto)
                enviar_mensaje(chat_id, respuesta)

        except requests.RequestException as error:
            # Mostramos solo el tipo de error para no imprimir el token.
            print(f"Error de conexión con Telegram ({type(error).__name__}). Reintento en 5 s...")
            time.sleep(5)


if __name__ == "__main__":
    main()