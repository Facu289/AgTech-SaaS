"""Configuración compartida de los tests.

Cada test usa una base de datos NUEVA y temporal: nunca se toca datos/agroapp.db.
Se corren desde la carpeta agroapp con:   python -m pytest
"""
import importlib
import sys
from pathlib import Path

import pytest

CARPETA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(CARPETA_PROYECTO))

# En orden: primero lo que no depende de nada, al final main.
MODULOS = [
    "app.nucleo.database", "app.nucleo.backup",
    "app.insumos.db", "app.maquinaria.db", "app.ganaderia.db", "app.lotes.db",
    "app.insumos.rutas", "app.maquinaria.rutas", "app.ganaderia.rutas", "app.lotes.rutas",
    "app.alertas", "app.exportar",
    "app.telegram.notas", "app.insumos.telegram", "app.maquinaria.telegram", "app.ganaderia.telegram",
    "app.telegram.lenguaje_natural", "app.telegram.comandos",
    "app.usuarios.db", "app.usuarios.rutas", "app.main",
]


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Arranca la app con una base vacía en una carpeta temporal y devuelve el módulo app.main."""
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "test.db"))
    # Los backups también van a la carpeta temporal, aunque el .env diga otra cosa.
    monkeypatch.setenv("AGROAPP_BACKUPS", str(tmp_path / "backups"))
    # Recargamos los módulos para que lean la nueva ruta de la base.
    for nombre in MODULOS:
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    return sys.modules["app.main"]


USUARIO_PRUEBA = ("prueba", "clave-de-prueba")


@pytest.fixture
def cliente_anonimo(app):
    """Un 'navegador de mentira' para llamar a la API sin levantar uvicorn. NO entró (sin login)."""
    from fastapi.testclient import TestClient
    return TestClient(app.app)


@pytest.fixture
def cliente(cliente_anonimo):
    """El mismo navegador de mentira, pero ya logueado (guarda la cookie de sesión)."""
    usuario, contrasena = USUARIO_PRUEBA
    sys.modules["app.usuarios.db"].guardar_usuario(usuario, contrasena)
    respuesta = cliente_anonimo.post("/login", json={"usuario": usuario, "contrasena": contrasena})
    assert respuesta.status_code == 200, respuesta.text
    return cliente_anonimo


@pytest.fixture
def bot(app):
    """Manda un mensaje como si viniera de Telegram y devuelve la respuesta."""
    return sys.modules["app.telegram.comandos"].generar_respuesta
