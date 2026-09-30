"""Punto de entrada: arma la API, traduce los errores a HTTP y sirve la web.

Se arranca desde la carpeta agroapp con:   uvicorn app.main:app --reload

Cada área está en su carpeta (app/insumos, app/maquinaria, app/ganaderia) con:
  db.py        -> el SQL
  rutas.py     -> los endpoints de la API (lo que usa la web)
  telegram.py  -> los comandos del bot
"""
import sqlite3
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import exportar
from app.alertas import obtener_alertas
from app.ganaderia import db as ganaderia_db
from app.ganaderia import rutas as ganaderia_rutas
from app.insumos import db as insumos_db
from app.insumos import rutas as insumos_rutas
from app.maquinaria import db as maquinaria_db
from app.maquinaria import rutas as maquinaria_rutas
from app.nucleo import backup, database, opciones
from app.nucleo.utilidades import formatear_cantidad
from app.telegram.comandos import generar_respuesta

# Al iniciar: primero un backup, después las tablas y migraciones.
# Si hay migraciones pendientes (la estructura de la base va a cambiar),
# SIEMPRE hacemos un backup antes, aunque ya haya uno de hoy.
database.verificar_ubicacion()
if database.migraciones_pendientes():
    ruta = backup.hacer_backup()
    print(f"Backup antes de actualizar la base: {ruta.name if ruta else '(base nueva)'}")
else:
    backup.hacer_backup(solo_si_no_hay_de_hoy=True)
database.crear_tablas()

app = FastAPI(title="AgroApp")
app.include_router(insumos_rutas.router)
app.include_router(maquinaria_rutas.router)
app.include_router(ganaderia_rutas.router)
app.include_router(exportar.router)


# ---------- Errores ----------
# Los archivos db_*.py lanzan excepciones propias (no saben nada de HTTP).
# Acá las traducimos a respuestas HTTP UNA sola vez, para todos los endpoints.

NO_ENCONTRADO = {
    insumos_db.InsumoNoEncontrado: "No existe ese insumo.",
    maquinaria_db.MaquinaNoEncontrada: "No existe esa máquina.",
    ganaderia_db.AnimalNoEncontrado: "No existe ese animal.",
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


@app.exception_handler(ganaderia_db.EventoInvalido)
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
