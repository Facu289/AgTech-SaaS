"""Entrar con Google (OAuth 2.0 / OpenID Connect, flujo "authorization code" con PKCE).

Cómo funciona, paso a paso:
1. El botón "Entrar con Google" va a /auth/google/inicio. Ahí inventamos dos códigos al azar:
   - state: para comprobar que la vuelta de Google corresponde a ESTE pedido (evita que otro
     sitio nos "meta" un login suyo).
   - verificador PKCE: un secreto que solo conoce nuestro servidor. A Google le mandamos su
     huella (sha256); al canjear el código mandamos el verificador. Si alguien roba el código
     en el camino, sin el verificador no le sirve.
   Los dos se guardan 10 minutos en una cookie HttpOnly y mandamos al navegador a Google.
2. La persona elige su cuenta en Google, y Google la devuelve a /auth/google/callback con un
   "code" y el mismo state.
3. Nuestro servidor canjea el code (con el secreto de la app y el verificador) directamente con
   Google y recibe un "id_token": un texto firmado que dice qué mail es.
4. SOLO entra si ese mail está cargado en un usuario ACTIVO (Ajustes > Usuarios).
   No se crean cuentas solas: Google dice QUIÉN es; nosotros decidimos si PUEDE entrar.

Variables del .env: GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET (si faltan, el botón no aparece).
GOOGLE_REDIRECT_URI es opcional: hace falta en el NAS (https://agro.grindnode.uk/auth/google/callback),
porque detrás de Cloudflare el servidor se ve a sí mismo como http.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.usuarios import db as usuarios_db
from app.usuarios import rutas as usuarios_rutas

router = APIRouter(tags=["Login"])

URL_AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
EMISORES = {"https://accounts.google.com", "accounts.google.com"}
COOKIE_GOOGLE = "agroapp_google"   # state + verificador, mientras la persona está en Google.
RUTA_COOKIE = "/auth/google"
MINUTOS_PARA_VOLVER = 10


class ErrorGoogle(Exception):
    """Google no confirmó la identidad (código vencido, respuesta rara, mail sin verificar...)."""


def _cliente():
    return os.getenv("GOOGLE_CLIENT_ID", "").strip(), os.getenv("GOOGLE_CLIENT_SECRET", "").strip()


def configurado():
    client_id, secreto = _cliente()
    return bool(client_id and secreto)


def direccion_de_vuelta(request: Request):
    """La "redirect URI": tiene que ser EXACTAMENTE una de las cargadas en Google Cloud."""
    fija = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    return fija or str(request.url_for("google_vuelta"))


def _base64url(datos: bytes):
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _pedir_token(code, verificador, redirect_uri):
    """Canjea el code por los tokens (pedido directo de nuestro servidor a Google)."""
    client_id, secreto = _cliente()
    try:
        respuesta = requests.post(
            URL_TOKEN,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": secreto,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verificador,
            },
            timeout=10,
        )
    except requests.RequestException as error:
        raise ErrorGoogle(f"No se pudo hablar con Google ({type(error).__name__}).")
    if respuesta.status_code != 200:
        raise ErrorGoogle(f"Google rechazó el código ({respuesta.status_code}).")
    return respuesta.json()


def leer_id_token(id_token):
    """Lee el id_token y revisa que sea para NUESTRA app, de Google, vigente y con mail verificado.

    No hace falta revisar la firma: lo recibimos directo de Google, por HTTPS, a cambio de nuestro
    secreto (así lo permite el estándar OpenID Connect). Sí revisamos sus datos.
    """
    try:
        partes = id_token.split(".")
        relleno = "=" * (-len(partes[1]) % 4)
        datos = json.loads(base64.urlsafe_b64decode(partes[1] + relleno))
    except (AttributeError, IndexError, ValueError):
        raise ErrorGoogle("El id_token no se pudo leer.")
    client_id, _ = _cliente()
    if datos.get("aud") != client_id:
        raise ErrorGoogle("El id_token es para otra aplicación.")
    if datos.get("iss") not in EMISORES:
        raise ErrorGoogle("El id_token no lo emitió Google.")
    if float(datos.get("exp", 0)) < time.time():
        raise ErrorGoogle("El id_token está vencido.")
    if datos.get("email_verified") not in (True, "true") or not datos.get("email"):
        raise ErrorGoogle("Google no confirmó el mail.")
    return datos


@router.get("/auth/google/disponible")
def disponible():
    """La página de login pregunta esto para mostrar (o no) el botón "Entrar con Google"."""
    return {"disponible": configurado()}


@router.get("/auth/google/inicio")
def ir_a_google(request: Request):
    if not configurado():
        raise HTTPException(404, "Entrar con Google no está configurado.")
    state = secrets.token_urlsafe(24)
    verificador = secrets.token_urlsafe(48)
    desafio = _base64url(hashlib.sha256(verificador.encode()).digest())
    client_id, _ = _cliente()
    parametros = {
        "client_id": client_id,
        "redirect_uri": direccion_de_vuelta(request),
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        "prompt": "select_account",  # Que siempre pregunte qué cuenta usar.
    }
    respuesta = RedirectResponse(f"{URL_AUTORIZAR}?{urlencode(parametros)}", status_code=303)
    respuesta.set_cookie(
        COOKIE_GOOGLE,
        f"{state}.{verificador}",  # token_urlsafe no usa puntos: el punto separa los dos.
        max_age=MINUTOS_PARA_VOLVER * 60,
        httponly=True,
        samesite="lax",  # Lax SÍ viaja cuando Google nos devuelve con un link común.
        secure=usuarios_rutas.cookie_segura(request),
        path=RUTA_COOKIE,
    )
    return respuesta


def _volver_al_login(motivo):
    respuesta = RedirectResponse(f"/web/login.html?error={motivo}", status_code=303)
    respuesta.delete_cookie(COOKIE_GOOGLE, path=RUTA_COOKIE)
    return respuesta


@router.get("/auth/google/callback", name="google_vuelta")
def vuelta_de_google(request: Request, code: str = "", state: str = "", error: str = ""):
    if not configurado():
        return _volver_al_login("google-no-configurado")
    if error:
        return _volver_al_login("google-cancelado")  # Ej: tocó "Cancelar" en Google.
    state_guardado, _, verificador = request.cookies.get(COOKIE_GOOGLE, "").partition(".")
    if not (code and state and state_guardado and verificador) or not hmac.compare_digest(state, state_guardado):
        return _volver_al_login("google-invalido")
    try:
        tokens = _pedir_token(code, verificador, direccion_de_vuelta(request))
        datos = leer_id_token(tokens.get("id_token", ""))
    except ErrorGoogle as problema:
        print(f"Entrar con Google falló: {problema}")
        return _volver_al_login("google-fallo")

    usuario = usuarios_db.usuario_por_email(datos["email"])
    if usuario is None:
        print("Entrar con Google: el mail no es de ningún usuario activo.")
        return _volver_al_login("google-no-autorizado")

    respuesta = RedirectResponse("/web/index.html", status_code=303)
    usuarios_rutas.poner_cookie_sesion(respuesta, usuarios_db.crear_sesion(usuario["id"]), request)
    respuesta.delete_cookie(COOKIE_GOOGLE, path=RUTA_COOKIE)
    return respuesta
