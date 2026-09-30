"""Tipos de datos reutilizables para los modelos de Pydantic.

"Annotated[tipo, BeforeValidator(funcion)]" significa: antes de validar el tipo,
pasá el valor por esta función. Así, por ejemplo, "2,5" (texto) se convierte en 2.5.
"""
from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import BeforeValidator, Field

from app.nucleo.utilidades import leer_numero, normalizar_texto


def _vacio_a_none(valor):
    """Un campo vacío de un formulario ("") significa "sin dato" (None)."""
    if isinstance(valor, str) and valor.strip() == "":
        return None
    return valor


def _numero_desde_texto(valor):
    """Acepta números (20, 2.5) o texto en formato argentino ("2,5", "1.500")."""
    valor = _vacio_a_none(valor)
    if isinstance(valor, str):
        numero = leer_numero(valor)
        if numero is None:
            raise ValueError("número inválido (usá, por ejemplo, 20 o 2,5)")
        return numero
    return valor


def _normalizar(valor):
    """'Agroquímico ' -> 'agroquimico' (para comparar con las opciones)."""
    return normalizar_texto(valor) if isinstance(valor, str) else valor


# Número >= 0, sin "infinito". Acepta "2,5".
Numero = Annotated[float, BeforeValidator(_numero_desde_texto), Field(ge=0, allow_inf_nan=False)]

def _numero_o_cero(valor):
    """Un campo numérico vacío vale 0 (ej: "Stock mínimo" sin completar)."""
    return 0 if _vacio_a_none(valor) is None else _numero_desde_texto(valor)


# Número >= 0 que, si viene vacío, vale 0.
NumeroOCero = Annotated[float, BeforeValidator(_numero_o_cero), Field(ge=0, allow_inf_nan=False)]

# Igual, pero puede quedar vacío (None).
# OJO: el "ge=0" va en el float de ADENTRO; si fuera afuera, Pydantic
# intentaría comparar None >= 0 y fallaría cuando el campo viene vacío.
NumeroOpcional = Annotated[
    Optional[Annotated[float, Field(ge=0, allow_inf_nan=False)]],
    BeforeValidator(_numero_desde_texto),
    Field(default=None),
]

# Una fecha 'AAAA-MM-DD' que puede venir vacía desde un <input type="date">.
FechaOpcional = Annotated[Optional[date], BeforeValidator(_vacio_a_none), Field(default=None)]

# Un número entero que puede venir vacío (un año, o el id de una máquina
# elegida en un <select> donde la opción "ninguna" tiene valor "").
EnteroOpcional = Annotated[Optional[int], BeforeValidator(_vacio_a_none), Field(default=None)]
IdOpcional = EnteroOpcional


def opcion(valores: dict):
    """Tipo que solo acepta las claves del diccionario (sin importar mayúsculas/tildes).

    opcion({"kg": ..., "litros": ...})  ->  solo "kg" o "litros".
    """
    return Annotated[Literal[tuple(valores)], BeforeValidator(_normalizar)]
