"""Configuración compartida de los tests.

Cada test usa una base de datos NUEVA y temporal: nunca se toca agroapp.db.
"""
import importlib
import sys
from pathlib import Path

import pytest

CARPETA_PROYECTO = Path(__file__).parent.parent
sys.path.insert(0, str(CARPETA_PROYECTO))


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Arranca la app con una base vacía en una carpeta temporal y devuelve el módulo main."""
    monkeypatch.setenv("AGROAPP_DB", str(tmp_path / "test.db"))
    # Recargamos los módulos para que lean la nueva ruta de la base.
    for nombre in ("database", "backup", "db_maquinaria", "db_ganaderia",
                   "insumos", "maquinaria", "ganaderia", "exportar", "lenguaje_natural", "main"):
        if nombre in sys.modules:
            importlib.reload(sys.modules[nombre])
        else:
            importlib.import_module(nombre)
    return sys.modules["main"]


@pytest.fixture
def cliente(app):
    """Un 'navegador de mentira' para llamar a la API sin levantar uvicorn."""
    from fastapi.testclient import TestClient
    return TestClient(app.app)


@pytest.fixture
def bot(app):
    """Manda un mensaje como si viniera de Telegram y devuelve la respuesta."""
    return app.generar_respuesta
