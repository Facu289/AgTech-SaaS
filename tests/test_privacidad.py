"""Política de privacidad: pública (sin login), con el contacto del .env."""
import sys

import pytest


@pytest.mark.parametrize("ruta", ["/privacidad", "/eliminar-datos"])
def test_es_publica_sin_login(cliente_anonimo, ruta):
    respuesta = cliente_anonimo.get(ruta, follow_redirects=False)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "Política de privacidad" in respuesta.text
    assert 'id="eliminar-datos"' in respuesta.text  # La sección que Meta pide para borrar datos.


def test_muestra_el_contacto_del_env(cliente_anonimo, monkeypatch):
    monkeypatch.setenv("AGROAPP_CONTACTO_PRIVACIDAD", "campo@ejemplo.com")
    texto = cliente_anonimo.get("/privacidad").text
    assert "campo@ejemplo.com" in texto
    assert "{{CONTACTO}}" not in texto


def test_sin_contacto_en_el_env_usa_el_de_siempre(cliente_anonimo, monkeypatch):
    monkeypatch.delenv("AGROAPP_CONTACTO_PRIVACIDAD", raising=False)
    texto = cliente_anonimo.get("/privacidad").text
    assert "facu012108@gmail.com" in texto
    assert "{{CONTACTO}}" not in texto


@pytest.mark.parametrize("archivo", ["/web/img/logo.png", "/web/img/favicon.png"])
def test_logo_e_icono_son_publicos(cliente_anonimo, archivo):
    """Se ven sin login: en /privacidad y en la pestaña de la página de login."""
    respuesta = cliente_anonimo.get(archivo)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"


def test_el_contacto_no_puede_meter_codigo(cliente_anonimo, monkeypatch):
    monkeypatch.setenv("AGROAPP_CONTACTO_PRIVACIDAD", "<script>alert(1)</script>")
    texto = cliente_anonimo.get("/privacidad").text
    assert "<script>" not in texto
    assert "&lt;script&gt;" in texto


def test_logo_solo_si_existe(app, cliente_anonimo, monkeypatch, tmp_path):
    privacidad = sys.modules["app.privacidad"]
    monkeypatch.setattr(privacidad, "LOGO", tmp_path / "no-existe.png")
    assert "<img" not in cliente_anonimo.get("/privacidad").text
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")
    monkeypatch.setattr(privacidad, "LOGO", logo)
    assert '<img src="/web/img/logo.png"' in cliente_anonimo.get("/privacidad").text
    assert "{{LOGO}}" not in cliente_anonimo.get("/privacidad").text


def test_liberar_privacidad_no_libera_lo_demas(cliente_anonimo):
    assert cliente_anonimo.get("/insumos").status_code == 401
    assert cliente_anonimo.get("/privacidad/../insumos").status_code == 401
    assert cliente_anonimo.get("/privacidadx").status_code in (401, 404)
