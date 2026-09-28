from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


# Forma de los datos que RECIBE el endpoint /mensaje.
class MensajeEntrada(BaseModel):
    texto: str


# Forma de los datos que DEVUELVE el endpoint /mensaje.
class MensajeSalida(BaseModel):
    respuesta: str


def generar_respuesta(texto: str) -> str:
    """El 'cerebro' de la app: decide qué contestar a cada mensaje."""
    texto = texto.strip()

    if texto == "/start":
        return "¡Hola! Soy el bot de AgroApp 🌱. Escribime algo y te respondo desde el backend."
    if texto == "/ayuda":
        return "Por ahora sé: /start, /ayuda y repetir lo que me escribas."
    return f"Backend recibió: {texto}"


@app.get("/")
def inicio():
    return {"mensaje": "Hola, la API de AgroApp está funcionando"}


@app.post("/mensaje", response_model=MensajeSalida)
def procesar_mensaje(mensaje: MensajeEntrada):
    return MensajeSalida(respuesta=generar_respuesta(mensaje.texto))