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
    "app.insumos.db", "app.maquinaria.db", "app.ganaderia.db",
    "app.insumos.rutas", "app.maquinaria.rutas", "app.ganaderia.rutas",
    "app.alertas", "app.exportar",
    "app.telegram.notas", "app.insumos.telegram", "app.maquinaria.telegram", "app.ganaderia.telegram",
    "app.telegram.lenguaje_natural", "app.telegram.comandos", "app.main",
]


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Arranca la app con una base vacía en una carpeta temporal y devuelve el módulo app.main."""
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "test.db"))
    # Recargamos los módulos para que lean la nueva ruta de la base.
    for nombre in MODULOS:
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    return sys.modules["app.main"]


@pytest.fixture
def cliente(app):
    """Un 'navegador de mentira' para llamar a la API sin levantar uvicorn."""
    from fastapi.testclient import TestClient
    return TestClient(app.app)


@pytest.fixture
def bot(app):
    """Manda un mensaje como si viniera de Telegram y devuelve la respuesta."""
    return sys.modules["app.telegram.comandos"].generar_respuesta
