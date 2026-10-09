"""Cosas de la web que conviene que no se rompan sin darnos cuenta."""
from pathlib import Path

import pytest

CARPETA_WEB = Path(__file__).parent.parent / "web"
PAGINAS = sorted(CARPETA_WEB.glob("*.html"))


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.name)
def test_toda_pagina_carga_el_modo_oscuro_antes_del_css(pagina):
    """Si una página no carga tema.js en el <head>, queda clara aunque elijas Oscuro."""
    html = pagina.read_text(encoding="utf-8")
    cabeza = html[: html.index("</head>")]
    assert '<script src="js/tema.js"></script>' in cabeza
    assert cabeza.index("js/tema.js") < cabeza.index("css/estilos.css")  # Antes de dibujar: sin "flash".


def test_las_paginas_y_archivos_de_la_web_piden_revisar_si_cambiaron(cliente):
    """Cache-Control: no-cache -> después de actualizar la app, el navegador no muestra versiones viejas."""
    for ruta in ("/web/index.html", "/web/js/comun.js", "/web/css/estilos.css", "/web/js/tema.js", "/web/ajustes.html"):
        assert cliente.get(ruta).headers.get("cache-control") == "no-cache", ruta


def test_el_login_tambien_pide_revisar_si_cambio(cliente_anonimo):
    assert cliente_anonimo.get("/web/login.html").headers.get("cache-control") == "no-cache"


def test_la_api_no_lleva_esa_cabecera(cliente):
    """Solo la web: a la API no le cambiamos nada."""
    assert cliente.get("/opciones").headers.get("cache-control") is None
