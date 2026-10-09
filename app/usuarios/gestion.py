"""Gestión de usuarios (página Ajustes > Usuarios). Solo para admins.

Ojo: esconder el botón en la web NO alcanza (cualquiera puede llamar a la API a mano).
Por eso CADA endpoint de acá revisa en el servidor que quien pide sea admin: si no, 403.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.usuarios import db as usuarios_db
from app.usuarios.rutas import COOKIE

Rol = Literal["admin", "usuario"]


def solo_admin(request: Request):
    """'Dependencia' de FastAPI: corre antes del endpoint. 403 = te conozco, pero no tenés permiso."""
    usuario = getattr(request.state, "usuario", None)
    if not usuario or usuario.get("rol") != "admin":
        raise HTTPException(403, "Solo un admin puede gestionar usuarios.")
    return usuario


router = APIRouter(prefix="/usuarios", tags=["Usuarios"], dependencies=[Depends(solo_admin)])


class UsuarioNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(max_length=usuarios_db.LARGO_MAXIMO_NOMBRE)
    email: str = ""
    rol: Rol = "usuario"
    contrasena: Optional[str] = None  # Opcional si va a entrar con Google.


class UsuarioEditado(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(max_length=usuarios_db.LARGO_MAXIMO_NOMBRE)
    email: str = ""
    rol: Rol
    activo: bool


class ContrasenaNueva(BaseModel):
    contrasena: str


def _traducir(funcion, *argumentos, **opciones):
    """Pasa los errores de las reglas a HTTP: dato inválido -> 400, regla de admins -> 409."""
    try:
        return funcion(*argumentos, **opciones)
    except usuarios_db.DatoInvalido as error:
        raise HTTPException(400, str(error))
    except usuarios_db.ReglaUsuarios as error:
        raise HTTPException(409, str(error))


@router.get("")
def listar():
    return usuarios_db.listar_usuarios()


@router.post("", status_code=201)
def crear(datos: UsuarioNuevo):
    return _traducir(usuarios_db.crear_usuario, datos.nombre, datos.email, datos.rol, datos.contrasena or None)


@router.put("/{usuario_id}")
def editar(usuario_id: int, datos: UsuarioEditado, admin=Depends(solo_admin)):
    return _traducir(
        usuarios_db.editar_usuario, usuario_id, datos.nombre, datos.email, datos.rol, datos.activo, admin["id"]
    )


@router.post("/{usuario_id}/contrasena", status_code=204)
def cambiar_contrasena(usuario_id: int, datos: ContrasenaNueva, request: Request, admin=Depends(solo_admin)):
    # Si el admin cambia la suya, no lo sacamos de la sesión que está usando ahora.
    conservar = request.cookies.get(COOKIE) if usuario_id == admin["id"] else None
    _traducir(usuarios_db.cambiar_contrasena, usuario_id, datos.contrasena, conservar_token=conservar)
