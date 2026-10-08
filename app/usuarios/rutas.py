"""Login: entrar, salir, quién soy, y el "portero" que protege la web y la API.

Cómo funciona:
1. La página web/login.html manda usuario y contraseña a POST /login.
2. Si están bien, el servidor crea una sesión y la manda en una cookie.
3. El navegador devuelve esa cookie SOLO en cada pedido a este servidor.
4. El portero (revisar_pedido, lo usa app/main.py) mira la cookie en CADA pedido:
   sin sesión válida, la web va al login y la API responde 401.

El bot de Telegram no tiene navegador ni cookie: se identifica con un token propio
(AGROAPP_BOT_TOKEN en el .env) y solo puede usar POST /mensaje.
"""
import hmac
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.usuarios import db as usuarios_db

router = APIRouter(tags=["Login"])

COOKIE = "agroapp_sesion"

# Lo único que se puede pedir sin haber entrado. Rutas EXACTAS (sin comodines):
# así nadie puede colarse con trucos como "/web/css/../index.html".
# /salud la usa Docker para saber si la app anda (no muestra datos).
# /whatsapp la llama Meta: no tiene cookie, se protege con la firma (ver app/whatsapp/rutas.py).
RUTAS_LIBRES = {"/login", "/logout", "/salud", "/whatsapp","/web/login.html", "/web/js/login.js", "/web/css/estilos.css"}

# Protección contra "probar contraseñas": después de 5 fallos seguidos para un mismo
# usuario, se bloquea ese usuario por 15 minutos. (Vive en memoria: se reinicia con el backend).
MAXIMO_FALLOS = 5
MINUTOS_BLOQUEO = 15
_fallos: dict[str, list[float]] = {}


def _fallos_recientes(nombre):
    limite = time.time() - MINUTOS_BLOQUEO * 60
    recientes = [momento for momento in _fallos.get(nombre, []) if momento > limite]
    _fallos[nombre] = recientes
    return recientes


def cookie_segura(request: Request):
    """Secure = la cookie solo viaja por HTTPS. En la PC (http://127.0.0.1) tiene que ir sin Secure,
    si no el navegador no la guarda. AGROAPP_COOKIE_SEGURA=1 la fuerza (detrás de un proxy HTTPS)."""
    return request.url.scheme == "https" or os.getenv("AGROAPP_COOKIE_SEGURA", "") == "1"


# ---------- Endpoints ----------

class DatosLogin(BaseModel):
    usuario: str
    contrasena: str


@router.post("/login")
def entrar(datos: DatosLogin, request: Request, response: Response):
    clave = datos.usuario.strip().lower()
    if len(_fallos_recientes(clave)) >= MAXIMO_FALLOS:
        raise HTTPException(429, f"Demasiados intentos fallidos. Esperá {MINUTOS_BLOQUEO} minutos.")

    usuario = usuarios_db.autenticar(datos.usuario, datos.contrasena)
    if usuario is None:
        _fallos[clave].append(time.time())
        if not usuarios_db.hay_usuarios():
            raise HTTPException(401, "Todavía no hay usuarios. Creá uno con: python -m app.usuarios.crear_usuario")
        # Mismo mensaje si el usuario no existe o si la contraseña está mal: no damos pistas.
        raise HTTPException(401, "Usuario o contraseña incorrectos.")

    _fallos.pop(clave, None)
    token = usuarios_db.crear_sesion(usuario["id"])
    response.set_cookie(
        COOKIE,
        token,
        max_age=usuarios_db.DIAS_SESION * 24 * 3600,
        httponly=True,        # JavaScript no la puede leer (si se cuela código malicioso, no la roba).
        samesite="lax",       # Otros sitios no pueden hacer pedidos "en tu nombre" con tu cookie.
        secure=cookie_segura(request),
        path="/",
    )
    return {"usuario": usuario["nombre"]}


@router.post("/logout", status_code=204)
def salir(request: Request, response: Response):
    usuarios_db.cerrar_sesion(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.get("/yo")
def quien_soy(request: Request):
    """El usuario que está usando la web (para mostrarlo en el menú)."""
    return {"usuario": request.state.usuario["nombre"]}


# ---------- El portero ----------

def es_el_bot(request: Request):
    """True si el pedido trae el token del bot: "Authorization: Bearer <AGROAPP_BOT_TOKEN>"."""
    esperado = os.getenv("AGROAPP_BOT_TOKEN", "").strip()
    recibido = request.headers.get("authorization", "")
    if not esperado or not recibido.startswith("Bearer "):
        return False
    return hmac.compare_digest(recibido.removeprefix("Bearer ").strip().encode(), esperado.encode())


def revisar_pedido(request: Request) -> Optional[Response]:
    """Devuelve None si el pedido puede pasar, o la respuesta para cortarlo (ir al login / 401)."""
    ruta = request.url.path
    if ruta in RUTAS_LIBRES:
        return None
    if ruta == "/mensaje" and request.method == "POST" and es_el_bot(request):
        return None

    usuario = usuarios_db.usuario_de_sesion(request.cookies.get(COOKIE))
    if usuario is not None:
        request.state.usuario = usuario
        return None

    # Sin sesión: si es una página (la abrió una persona), la mandamos al login.
    if request.method == "GET" and (ruta in ("/", "/docs", "/redoc") or ruta.startswith("/web")):
        return RedirectResponse("/web/login.html", status_code=303)
    # Si es la API (la llamó JavaScript o el bot), respondemos 401 y la web se encarga.
    return JSONResponse(status_code=401, content={"detail": "Tenés que iniciar sesión."})
