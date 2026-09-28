import sqlite3
import unicodedata
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
import database

# Crea las tablas al iniciar el servidor (si ya existen, no hace nada).
database.crear_tablas()

app = FastAPI()

# Valores permitidos. Para agregar uno nuevo, sumalo a la lista.
Categoria = Literal[
    "agroquimico", "semilla", "fertilizante", "combustible",
    "repuesto", "balanceado", "medicamento", "otro",
]
Unidad = Literal["kg", "litros", "bolsas", "unidades"]


# ---------- Modelos de datos ----------

class MensajeEntrada(BaseModel):
    texto: str


class MensajeSalida(BaseModel):
    respuesta: str


class InsumoNuevo(BaseModel):
    """Lo que hay que mandar para crear un insumo."""
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    categoria: Categoria
    unidad: Unidad
    cantidad: float = Field(default=0, ge=0)

    @field_validator("categoria", "unidad", mode="before")
    @classmethod
    def normalizar(cls, valor):
        """Pasa a minúsculas y saca tildes: 'Agroquímico' -> 'agroquimico'."""
        if not isinstance(valor, str):
            return valor
        sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
        return sin_tildes.strip().lower()

class Insumo(InsumoNuevo):
    """Un insumo ya guardado (tiene id)."""
    id: int


# ---------- Lógica del bot ----------

def generar_respuesta(texto: str) -> str:
    """El 'cerebro' de la app: decide qué contestar a cada mensaje."""
    texto = texto.strip()

    if texto == "/start":
        return "¡Hola! Soy el bot de AgroApp 🌱. Escribime algo y te respondo desde el backend."
    if texto == "/ayuda":
        return "Por ahora sé: /start, /ayuda y repetir lo que me escribas."
    return f"Backend recibió: {texto}"


# ---------- Endpoints ----------

@app.get("/")
def inicio():
    return {"mensaje": "Hola, la API de AgroApp está funcionando"}


@app.post("/mensaje", response_model=MensajeSalida)
def procesar_mensaje(mensaje: MensajeEntrada):
    return MensajeSalida(respuesta=generar_respuesta(mensaje.texto))


@app.post("/insumos", response_model=Insumo, status_code=201)
def crear_insumo(insumo: InsumoNuevo):
    try:
        return database.agregar_insumo(
            insumo.nombre, insumo.categoria, insumo.unidad, insumo.cantidad
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Ya existe un insumo llamado '{insumo.nombre}'")


@app.get("/insumos", response_model=list[Insumo])
def ver_insumos():
    return database.listar_insumos()