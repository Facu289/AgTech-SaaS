"""Punto de entrada: arma la API, traduce los errores a HTTP y sirve la web.

Se arranca desde la carpeta agroapp con:   uvicorn app.main:app --reload

Cada área está en su carpeta (app/insumos, app/maquinaria, app/ganaderia) con:
  db.py        -> el SQL
  rutas.py     -> los endpoints de la API (lo que usa la web)
  telegram.py  -> los comandos del bot
"""
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import actividad, exportar, privacidad
from app.alertas import obtener_alertas
from app.ganaderia import db as ganaderia_db
from app.ganaderia import rutas as ganaderia_rutas
from app.insumos import db as insumos_db
from app.insumos import rutas as insumos_rutas
from app.lotes import db as lotes_db
from app.lotes import rutas as lotes_rutas
from app.ordenes import db as ordenes_db
from app.ordenes import rutas as ordenes_rutas
from app.maquinaria import db as maquinaria_db
from app.maquinaria import rutas as maquinaria_rutas
from app.nucleo import backup, database, opciones
from app.nucleo.utilidades import formatear_cantidad
from app.telegram.comandos import generar_respuesta
from app.usuarios import rutas as usuarios_rutas
from app.whatsapp import rutas as whatsapp_rutas

load_dotenv()  # Variables del .env (ej: AGROAPP_BOT_TOKEN).

# Al iniciar: primero un backup, después las tablas y migraciones (ver backup.preparar_base).
backup.preparar_base()


@asynccontextmanager
async def al_prender_y_apagar(app):
    """Corre al prender el backend (antes del yield) y al apagarlo (después).

    En el NAS el backend queda prendido semanas: el backup "de cada día" no puede depender
    de que se reinicie. Por eso dejamos una tarea de fondo que lo revisa cada hora.
    """
    tarea = asyncio.create_task(backup.backup_diario_continuo())
    yield
    tarea.cancel()


app = FastAPI(title="AgroApp", lifespan=al_prender_y_apagar)
app.include_router(insumos_rutas.router)
app.include_router(maquinaria_rutas.router)
app.include_router(ganaderia_rutas.router)
app.include_router(lotes_rutas.router)
app.include_router(ordenes_rutas.router)
app.include_router(exportar.router)
app.include_router(actividad.router)
app.include_router(usuarios_rutas.router)
app.include_router(whatsapp_rutas.router)
app.include_router(privacidad.router)


# ---------- Login ----------
# Un "middleware" corre ANTES de cada pedido. Este es el portero: si no hay sesión
# (ni es el bot con su token), corta el pedido acá y no llega a ningún endpoint.
@app.middleware("http")
async def exigir_login(request: Request, call_next):
    corte = usuarios_rutas.revisar_pedido(request)
    if corte is not None:
        return corte
    return await call_next(request)


# ---------- Errores ----------
# Los archivos db_*.py lanzan excepciones propias (no saben nada de HTTP).
# Acá las traducimos a respuestas HTTP UNA sola vez, para todos los endpoints.

NO_ENCONTRADO = {
    insumos_db.InsumoNoEncontrado: "No existe ese insumo.",
    maquinaria_db.MaquinaNoEncontrada: "No existe esa máquina.",
    ganaderia_db.AnimalNoEncontrado: "No existe ese animal.",
    lotes_db.LoteNoEncontrado: "No existe ese lote.",
    ordenes_db.OrdenNoEncontrada: "No existe esa orden de trabajo.",
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


@app.exception_handler(insumos_db.StockInsuficiente)
def error_stock(request: Request, error: insumos_db.StockInsuficiente):
    return _error(400, f"Stock insuficiente: hay {formatear_cantidad(error.disponible)}")


@app.exception_handler(ordenes_db.EstadoInvalido)
def error_estado_orden(request: Request, error):
    return _error(409, str(error))


@app.exception_handler(ganaderia_db.EventoInvalido)
def error_evento(request: Request, error):
    return _error(400, str(error))


@app.exception_handler(ganaderia_rutas.CaravanaRepetida)
def error_caravana_repetida(request: Request, error):
    """409 con una marca extra: la web pregunta "¿guardarlo igual?" y reintenta confirmando."""
    return JSONResponse(status_code=409, content={"detail": str(error), "caravana_repetida": True})


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


@app.get("/salud")
def salud():
    """¿Anda la app? Docker la consulta cada tanto (healthcheck). No pide login ni muestra datos.

    Además de responder, prueba leer la base: si la base no se puede abrir, contesta 503.
    """
    try:
        with database.conectar() as conexion:
            conexion.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return _error(503, "La base de datos no responde.")
    return {"estado": "ok"}


@app.get("/opciones")
def ver_opciones():
    """Todas las listas de valores permitidos (la web las usa para los desplegables)."""
    return opciones.todas()


@app.get("/alertas")
def ver_alertas():
    """Lo que requiere atención: stock bajo, vencimientos, services y partos."""
    return obtener_alertas()


# ---------- Telegram ----------
# bot/bot.py manda cada mensaje acá; la lógica está en app/telegram/.

class MensajeEntrada(BaseModel):
    texto: str
    usuario: Optional[int] = None  # Id de Telegram de quien escribe (para confirmar con "sí").


class MensajeSalida(BaseModel):
    respuesta: str


@app.post("/mensaje", response_model=MensajeSalida)
def procesar_mensaje(mensaje: MensajeEntrada):
    return MensajeSalida(respuesta=generar_respuesta(mensaje.texto, mensaje.usuario))


# ---------- Web ----------
# Sirve la carpeta "web" en http://127.0.0.1:8000/web/
# (va al final para que no tape ningún endpoint de la API).
CARPETA_WEB = database.CARPETA_PROYECTO / "web"
app.mount("/web", StaticFiles(directory=CARPETA_WEB, html=True), name="web")
