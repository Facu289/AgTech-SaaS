"""Punto de entrada: arma la API, reparte los comandos de Telegram y sirve la web.

La lógica de cada área está en su propio archivo:
  insumos.py    -> insumos, movimientos y notas
  maquinaria.py -> máquinas, services, trabajos, vencimientos y contactos
  ganaderia.py  -> animales y sus eventos
"""
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import backup
import database
import db_ganaderia
import db_maquinaria
import exportar
import ganaderia
import insumos
import lenguaje_natural
import maquinaria
import opciones
from utilidades import dias_hasta, formatear_cantidad

# Al iniciar: primero un backup, después las tablas y migraciones.
# Si hay migraciones pendientes (la estructura de la base va a cambiar),
# SIEMPRE hacemos un backup antes, aunque ya haya uno de hoy.
if database.migraciones_pendientes():
    ruta = backup.hacer_backup()
    print(f"Backup antes de actualizar la base: {ruta.name if ruta else '(base nueva)'}")
else:
    backup.hacer_backup(solo_si_no_hay_de_hoy=True)
database.crear_tablas()

app = FastAPI(title="AgroApp")
app.include_router(insumos.router)
app.include_router(maquinaria.router)
app.include_router(ganaderia.router)
app.include_router(exportar.router)


# ---------- Errores ----------
# Los archivos db_*.py lanzan excepciones propias (no saben nada de HTTP).
# Acá las traducimos a respuestas HTTP UNA sola vez, para todos los endpoints.

NO_ENCONTRADO = {
    database.InsumoNoEncontrado: "No existe ese insumo.",
    db_maquinaria.MaquinaNoEncontrada: "No existe esa máquina.",
    db_ganaderia.AnimalNoEncontrado: "No existe ese animal.",
}


def _error(codigo: int, mensaje: str):
    return JSONResponse(status_code=codigo, content={"detail": mensaje})


@app.exception_handler(database.NoEncontrado)
def error_no_encontrado(request: Request, error: database.NoEncontrado):
    return _error(404, str(error) or NO_ENCONTRADO.get(type(error), "No existe (puede que ya se haya borrado)."))


@app.exception_handler(database.TieneHistorial)
def error_tiene_historial(request: Request, error):
    return _error(409, "Tiene historial, así que no se puede eliminar: archivalo o dalo de baja.")


@app.exception_handler(database.Archivado)
def error_archivado(request: Request, error):
    return _error(409, "Está archivado o dado de baja: reactivalo para poder usarlo.")


@app.exception_handler(database.StockInsuficiente)
def error_stock(request: Request, error: database.StockInsuficiente):
    return _error(400, f"Stock insuficiente: hay {formatear_cantidad(error.disponible)}")


@app.exception_handler(db_ganaderia.EventoInvalido)
def error_evento(request: Request, error):
    return _error(400, str(error))


@app.exception_handler(sqlite3.IntegrityError)
def error_integridad(request: Request, error):
    """Última red de seguridad: la base rechazó el dato (nombre repetido, relación inválida...)."""
    if "UNIQUE" in str(error):
        return _error(409, "Ya existe un registro con ese nombre.")
    return _error(400, "La base de datos rechazó el dato (revisá que lo elegido exista).")


# ---------- Endpoints generales ----------

@app.get("/")
def inicio():
    return RedirectResponse("/web/")


@app.get("/opciones")
def ver_opciones():
    """Todas las listas de valores permitidos (la web las usa para los desplegables)."""
    return opciones.todas()


@app.get("/alertas")
def ver_alertas():
    """Lo que requiere atención: stock bajo, vencimientos y partos próximos."""
    return {
        "stock_bajo": insumos.insumos_con_stock_bajo(),
        "vencimientos": [
            {**v, "dias": dias_hasta(v["fecha_vencimiento"])} for v in maquinaria.vencimientos_para_alertar()
        ],
        "partos": [
            {**a, "dias": dias_hasta(a["fecha_probable_parto"])} for a in ganaderia.partos_para_alertar()
        ],
        "services": db_maquinaria.services_para_alertar(),
    }


# ---------- Telegram ----------

class MensajeEntrada(BaseModel):
    texto: str
    usuario: Optional[int] = None  # Id de Telegram de quien escribe (para confirmar con "sí").


class MensajeSalida(BaseModel):
    respuesta: str


def comando_alertas(argumento: str) -> str:
    alertas = ver_alertas()
    lineas = ["🔔 Alertas"]
    if alertas["stock_bajo"]:
        lineas.append("\n📦 Stock bajo")
        for i in alertas["stock_bajo"]:
            lineas.append(
                f"  • {i['nombre']}: {formatear_cantidad(i['cantidad'])} {i['unidad']} "
                f"(mínimo {formatear_cantidad(i['stock_minimo'])})"
            )
    if alertas["vencimientos"]:
        lineas.append("\n📅 Vencimientos")
        lineas += ["  " + maquinaria._linea_vencimiento(v) for v in alertas["vencimientos"]]
    if alertas["services"]:
        lineas.append("\n🔧 Services")
        lineas += [f"  {p['maquina_nombre']}: " + maquinaria._describir_plan(p) for p in alertas["services"]]
    if alertas["partos"]:
        lineas.append("\n🍼 Partos")
        lineas += ["  " + linea for linea in ganaderia.lineas_partos(alertas["partos"])]
    if len(lineas) == 1:
        return "🔔 No hay alertas. Todo en orden. 👌"
    return "\n".join(lineas)


AYUDA = """Comandos de AgroApp

📦 Stock
/stock [filtro] - ver stock (ej: /stock herbicida)
/repuestos [filtro] - ver repuestos
/nuevo <nombre> <categoría o tipo> <unidad>
/entrada <cantidad> <insumo> - motivo
/salida <cantidad> <insumo> - motivo

🚜 Maquinaria
/maquinas [filtro] - horas y últimos services
/horas <máquina> <horas> - actualizar horómetro
/trabajo <máquina> <ha> <tipo> - lote
/service <máquina> - descripción
/arreglo <máquina> - descripción
/services [máquina] - service programado
/vencimientos - seguros, licencias, VTV...

🐄 Animales
/animales [filtro] - resumen o lista
/animal <caravana> - ficha
/parto <caravana> <crías: m/h> - detalle
/tacto <caravana> <preñada|vacía> [fecha parto]
/servicio <caravana> - toro o IA
/aborto <caravana> - detalle

📝 Otros
/alertas - todo lo que requiere atención
💬 También podés escribir normal: "gasté 20 litros de glifosato en el lote 4"
/nota <texto> · /notas · /hecha <n>
/ayuda - esta ayuda"""

# Qué función responde cada comando. Todas reciben el texto después del comando.
COMANDOS = {
    "/start": lambda _: "¡Hola! Soy el bot de AgroApp 🌱. Escribí /ayuda para ver qué sé hacer.",
    "/ayuda": lambda _: AYUDA,
    "/stock": insumos.comando_stock,
    "/repuestos": insumos.comando_repuestos,
    "/nuevo": insumos.comando_nuevo,
    "/entrada": lambda arg: insumos.comando_movimiento("entrada", arg),
    "/salida": lambda arg: insumos.comando_movimiento("salida", arg),
    "/nota": insumos.comando_nota,
    "/notas": insumos.comando_notas,
    "/hecha": insumos.comando_hecha,
    "/maquinas": maquinaria.comando_maquinas,
    "/horas": maquinaria.comando_horas,
    "/trabajo": maquinaria.comando_trabajo,
    "/service": lambda arg: maquinaria.comando_mantenimiento("service", arg),
    "/arreglo": lambda arg: maquinaria.comando_mantenimiento("arreglo", arg),
    "/vencimientos": maquinaria.comando_vencimientos,
    "/services": maquinaria.comando_services,
    "/animales": ganaderia.comando_animales,
    "/animal": ganaderia.comando_animal,
    "/parto": ganaderia.comando_parto,
    "/aborto": ganaderia.comando_aborto,
    "/tacto": ganaderia.comando_tacto,
    "/servicio": ganaderia.comando_servicio,
    "/alertas": comando_alertas,
}

# Telegram no acepta mensajes de más de 4096 caracteres.
LARGO_MAXIMO = 4000


def ejecutar_comando(texto: str) -> str:
    """Corre UN comando ("/stock herbicida") y devuelve la respuesta."""
    texto = texto.strip()

    # Separa "/nota comprar urea" en comando="/nota" y argumento="comprar urea".
    partes = texto.split(maxsplit=1)
    comando = partes[0].lower().split("@")[0] if partes else ""  # "/Stock@mi_bot" -> "/stock"
    argumento = partes[1].strip() if len(partes) > 1 else ""

    funcion = COMANDOS.get(comando)
    if funcion is None:
        return f"No entendí '{texto}'. Escribí /ayuda para ver los comandos."
    return funcion(argumento)


def generar_respuesta(texto: str, usuario: Optional[int] = None) -> str:
    """El 'cerebro' del bot: decide qué contestar a cada mensaje.

    - Si empieza con "/", es un comando.
    - Si no (o es /si, /no), es lenguaje natural: lo interpreta Gemini.
    """
    texto = texto.strip()
    primera = texto.split(maxsplit=1)[0].lower().split("@")[0] if texto else ""
    if texto.startswith("/") and primera not in ("/si", "/no"):
        respuesta = ejecutar_comando(texto)
    elif not texto:
        respuesta = "Escribí /ayuda para ver qué sé hacer."
    else:
        texto_natural = primera[1:] if primera in ("/si", "/no") else texto
        respuesta = lenguaje_natural.interpretar(texto_natural, usuario or 0, AYUDA, ejecutar_comando)

    if len(respuesta) > LARGO_MAXIMO:
        respuesta = respuesta[:LARGO_MAXIMO].rsplit("\n", 1)[0] + "\n\n… (cortado: usá un filtro o mirá la web)"
    return respuesta


@app.post("/mensaje", response_model=MensajeSalida)
def procesar_mensaje(mensaje: MensajeEntrada):
    return MensajeSalida(respuesta=generar_respuesta(mensaje.texto, mensaje.usuario))


# ---------- Web ----------
# Sirve los archivos de la carpeta "static" en http://127.0.0.1:8000/web/
# (va al final para que no tape ningún endpoint de la API).
CARPETA_WEB = Path(__file__).parent / "static"
app.mount("/web", StaticFiles(directory=CARPETA_WEB, html=True), name="web")
