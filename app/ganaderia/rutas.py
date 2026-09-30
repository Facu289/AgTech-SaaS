"""Ganadería (vacunos, uno por caravana): modelos de datos, reglas y endpoints de la API."""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ganaderia import db as ganaderia_db
from app.nucleo.opciones import CATEGORIAS_ANIMAL, DIAS_ALERTA, ESTADOS_ANIMAL, ESTADOS_REPRODUCTIVOS, TIPOS_EVENTO
from app.nucleo.tipos import FechaOpcional, IdOpcional, opcion
from app.nucleo.utilidades import normalizar_texto

router = APIRouter(tags=["Ganadería"])


# ---------- Modelos ----------

class AnimalDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    caravana: str = Field(min_length=1, max_length=30)
    categoria: opcion(CATEGORIAS_ANIMAL)
    raza: str = Field(default="", max_length=60)
    rodeo: str = Field(default="", max_length=60)  # Lote, potrero o grupo.
    fecha_nacimiento: FechaOpcional = None
    estado_reproductivo: opcion(ESTADOS_REPRODUCTIVOS) = ""
    fecha_probable_parto: FechaOpcional = None
    madre_id: IdOpcional = None
    estado: opcion(ESTADOS_ANIMAL) = "activo"
    observaciones: str = Field(default="", max_length=1000)


class EventoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date = Field(default_factory=date.today)
    tipo: opcion(TIPOS_EVENTO)
    resultado: Literal["", "prenada", "vacia"] = ""  # Solo para tacto.
    crias_machos: int = Field(default=0, ge=0, le=5)  # Solo para parto.
    crias_hembras: int = Field(default=0, ge=0, le=5)
    detalle: str = Field(default="", max_length=500)
    fecha_probable_parto: FechaOpcional = None  # Opcional en un tacto positivo.

    @field_validator("resultado", mode="before")
    @classmethod
    def normalizar_resultado(cls, valor):
        """"Preñada" -> "prenada" (normalizar_texto saca tildes y la ñ)."""
        return normalizar_texto(valor) if isinstance(valor, str) else valor


# ---------- Reglas compartidas ----------

def animal_por_caravana(caravana: str, excluir_id=None):
    buscada = normalizar_texto(caravana)
    for a in ganaderia_db.listar_animales(incluir_bajas=True):
        if a["id"] != excluir_id and normalizar_texto(a["caravana"]) == buscada:
            return a
    return None


def _revisar_caravana(caravana, excluir_id=None):
    existente = animal_por_caravana(caravana, excluir_id)
    if existente:
        raise HTTPException(status_code=409, detail=f"Ya existe un animal con la caravana '{existente['caravana']}'")


def partos_para_alertar():
    return ganaderia_db.partos_proximos(date.today() + timedelta(days=DIAS_ALERTA))


# ---------- Endpoints ----------

@router.get("/animales")
def ver_animales(incluir_bajas: bool = False):
    return ganaderia_db.listar_animales(incluir_bajas)


@router.post("/animales", status_code=201)
def crear_animal(datos: AnimalDatos):
    _revisar_caravana(datos.caravana)
    return ganaderia_db.agregar_animal(datos.model_dump())


@router.get("/animales/{animal_id}")
def ver_ficha_animal(animal_id: int):
    animal = ganaderia_db.obtener_animal(animal_id)
    if animal is None:
        raise ganaderia_db.AnimalNoEncontrado()
    return {
        "animal": animal,
        "eventos": ganaderia_db.listar_eventos(animal_id),
        "crias": ganaderia_db.listar_crias(animal_id),
    }


@router.put("/animales/{animal_id}")
def editar_animal(animal_id: int, datos: AnimalDatos):
    _revisar_caravana(datos.caravana, animal_id)
    return ganaderia_db.editar_animal(animal_id, datos.model_dump())


@router.delete("/animales/{animal_id}", status_code=204)
def eliminar_animal(animal_id: int):
    ganaderia_db.eliminar_animal(animal_id)


@router.post("/animales/{animal_id}/eventos", status_code=201)
def crear_evento(animal_id: int, evento: EventoNuevo):
    """Registra un evento y devuelve el animal actualizado."""
    return ganaderia_db.registrar_evento(
        animal_id, evento.fecha, evento.tipo, evento.resultado, evento.crias_machos,
        evento.crias_hembras, evento.detalle, evento.fecha_probable_parto,
    )


@router.delete("/eventos-animales/{evento_id}", status_code=204)
def eliminar_evento(evento_id: int):
    ganaderia_db.eliminar_evento(evento_id)
