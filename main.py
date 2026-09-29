import math
import re
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
        return normalizar_texto(valor)

class Insumo(InsumoNuevo):
    """Un insumo ya guardado (tiene id)."""
    id: int

# ---------- Funciones de ayuda ----------

def normalizar_texto(valor: str) -> str:
    """Pasa a minúsculas y saca tildes: ' Agroquímico ' -> 'agroquimico'."""
    sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower()


def leer_cantidad(texto: str):
    """Convierte lo que escribe el usuario en número. Devuelve None si no es válido.

    Acepta: 20 | 2.5 | 2,5 | 1.500 (mil quinientos) | 1.500,5
    """
    texto = texto.strip()
    if "," in texto:
        # Formato argentino: el punto separa miles y la coma los decimales.
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        # "1.500" o "12.000": los puntos son separadores de miles.
        texto = texto.replace(".", "")
    try:
        cantidad = float(texto)
    except ValueError:
        return None
    if not math.isfinite(cantidad) or cantidad <= 0:
        return None
    return cantidad

# ---------- Lógica del bot ----------

EMOJIS_CATEGORIA = {
    "agroquimico": "🧪", "semilla": "🌱", "fertilizante": "🧂", "combustible": "⛽",
    "repuesto": "🔧", "balanceado": "🌾", "medicamento": "💉", "otro": "📦",
}


def formatear_cantidad(cantidad: float):
    """1500.0 -> 1500 | 2.5 -> 2.5 (saca el .0 cuando no hace falta)."""
    return int(cantidad) if cantidad.is_integer() else round(cantidad, 2)


def texto_stock() -> str:
    """Arma el mensaje de stock agrupado por categoría."""
    insumos = database.listar_insumos()  # Ya vienen ordenados por categoría.
    if not insumos:
        return "No hay insumos cargados todavía."

    lineas = ["📋 Stock de insumos"]
    categoria_actual = None
    for insumo in insumos:
        if insumo["categoria"] != categoria_actual:
            categoria_actual = insumo["categoria"]
            emoji = EMOJIS_CATEGORIA.get(categoria_actual, "📦")
            lineas.append(f"\n{emoji} {categoria_actual.capitalize()}")
        cantidad = formatear_cantidad(insumo["cantidad"])
        lineas.append(f"  • {insumo['nombre']}: {cantidad} {insumo['unidad']}")
    return "\n".join(lineas)


def texto_notas() -> str:
    """Arma el mensaje con las notas pendientes."""
    notas = database.listar_notas_pendientes()
    if not notas:
        return "No hay notas pendientes. 🎉"

    lineas = ["📝 Notas pendientes"]
    for nota in notas:
        fecha = datetime.strptime(nota["creada_en"], "%Y-%m-%d %H:%M:%S")
        lineas.append(f"#{nota['id']} ({fecha:%d/%m %H:%M}) {nota['texto']}")
    lineas.append("\nPara cerrar una: /hecha <número>")
    return "\n".join(lineas)


def comando_nota(argumento: str) -> str:
    if not argumento:
        return "Escribí la nota después del comando.\nEjemplo: /nota comprar 20 bolsas de urea"
    nota_id = database.agregar_nota(argumento)
    return f"📝 Nota #{nota_id} guardada."


def comando_hecha(argumento: str) -> str:
    if not argumento.isdigit():
        return "Indicá el número de la nota.\nEjemplo: /hecha 3"
    nota_id = int(argumento)
    if database.marcar_nota_hecha(nota_id):
        return f"✅ Nota #{nota_id} marcada como hecha."
    return f"No encontré una nota pendiente con el número {nota_id}."


def buscar_insumos(texto: str) -> list:
    """Busca insumos por nombre sin importar mayúsculas ni tildes.

    Si hay uno con el nombre exacto, devuelve solo ese.
    Si no, devuelve todos los que CONTIENEN el texto ("glifo" -> "Glifosato").
    """
    buscado = normalizar_texto(texto)
    insumos = database.listar_insumos()
    exactos = [i for i in insumos if normalizar_texto(i["nombre"]) == buscado]
    if exactos:
        return exactos
    return [i for i in insumos if buscado in normalizar_texto(i["nombre"])]


def comando_movimiento(tipo: str, argumento: str) -> str:
    """Maneja /entrada y /salida. Formato: <cantidad> <insumo> [- motivo]"""
    uso = (
        f"Formato: /{tipo} <cantidad> <insumo> - <motivo opcional>\n"
        f"Ejemplo: /{tipo} 20 urea - compra"
    )
    partes = argumento.split(maxsplit=1)
    if len(partes) < 2:
        return uso

    cantidad = leer_cantidad(partes[0])
    if cantidad is None:
        return f"'{partes[0]}' no es una cantidad válida.\n{uso}"

    # "urea - compra" -> nombre="urea", motivo="compra"
    nombre, _, motivo = partes[1].partition(" -")
    nombre, motivo = nombre.strip(), motivo.strip() or "Telegram"
    if not nombre:
        return uso

    encontrados = buscar_insumos(nombre)
    if not encontrados:
        return f"No encontré ningún insumo que coincida con '{nombre}'. Mirá /stock."
    if len(encontrados) > 1:
        opciones = "\n".join(f"  • {i['nombre']}" for i in encontrados)
        return f"Encontré varios insumos con '{nombre}':\n{opciones}\nEscribí el nombre más completo."

    insumo = encontrados[0]
    try:
        actualizado = database.registrar_movimiento(insumo["id"], tipo, cantidad, motivo)
    except database.StockInsuficiente as error:
        disponible = formatear_cantidad(error.disponible)
        return f"⚠️ No alcanza el stock de {insumo['nombre']}: hay {disponible} {insumo['unidad']}."

    signo = "+" if tipo == "entrada" else "-"
    return (
        f"✅ {tipo.capitalize()} registrada: {signo}{formatear_cantidad(cantidad)} "
        f"{insumo['unidad']} de {insumo['nombre']} ({motivo})\n"
        f"Stock actual: {formatear_cantidad(actualizado['cantidad'])} {insumo['unidad']}"
    )


AYUDA = """Comandos:
/stock - ver el stock de insumos
/entrada <cantidad> <insumo> - sumar stock
/salida <cantidad> <insumo> - restar stock
(opcional: agregá " - motivo" al final)
/nota <texto> - guardar una nota
/notas - ver notas pendientes
/hecha <número> - marcar una nota como hecha
/ayuda - esta ayuda"""

def generar_respuesta(texto: str) -> str:
    """El 'cerebro' de la app: decide qué contestar a cada mensaje."""
    texto = texto.strip()

    # Separa "/nota comprar urea" en comando="/nota" y argumento="comprar urea".
    partes = texto.split(maxsplit=1)
    comando = partes[0].lower().split("@")[0] if partes else ""  # "/Stock@mi_bot" -> "/stock"
    argumento = partes[1].strip() if len(partes) > 1 else ""

    if comando == "/start":
        return "¡Hola! Soy el bot de AgroApp 🌱. Escribí /ayuda para ver qué sé hacer."
    if comando == "/ayuda":
        return AYUDA
    if comando == "/stock":
        return texto_stock()
    if comando in ("/entrada", "/salida"):
        return comando_movimiento(comando[1:], argumento)
    if comando == "/nota":
        return comando_nota(argumento)
    if comando == "/notas":
        return texto_notas()
    if comando == "/hecha":
        return comando_hecha(argumento)
    return f"No entendí '{texto}'. Escribí /ayuda para ver los comandos."
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