"""Política de privacidad: una página pública (sin login) que Meta pide para publicar la app.

/privacidad      -> la política completa
/eliminar-datos  -> la misma página (Meta pide además una "URL de eliminación de datos";
                    la sección está en la misma página, con el id "eliminar-datos")

El texto está en app/privacidad.html. El mail de contacto es CONTACTO_POR_DEFECTO; se puede
cambiar sin tocar el código con AGROAPP_CONTACTO_PRIVACIDAD en el .env.
"""
import html
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Privacidad"])

PLANTILLA = Path(__file__).parent / "privacidad.html"
# El logo vive con la web. Es público (está en RUTAS_LIBRES) para que se vea sin login.
LOGO = Path(__file__).parent.parent / "web" / "img" / "logo.png"
CONTACTO_POR_DEFECTO = "facu012108@gmail.com"


def armar_pagina() -> str:
    contacto = os.getenv("AGROAPP_CONTACTO_PRIVACIDAD", "").strip() or CONTACTO_POR_DEFECTO
    # Si todavía no está el logo, la página sale igual, sin imagen.
    logo = '<img src="/web/img/logo.png" alt="Logo de AgroApp">' if LOGO.exists() else ""
    return (
        PLANTILLA.read_text(encoding="utf-8")
        .replace("{{LOGO}}", logo)
        # html.escape: si el valor del .env tuviera "<" o ">", se muestra como texto y no como código.
        .replace("{{CONTACTO}}", html.escape(contacto))
    )


@router.get("/privacidad", response_class=HTMLResponse)
@router.get("/eliminar-datos", response_class=HTMLResponse)
def ver_privacidad():
    return armar_pagina()
