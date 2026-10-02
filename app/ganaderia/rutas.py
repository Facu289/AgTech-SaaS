"""Ganadería (especies que crea el usuario; animales por caravana o en grupo): modelos, reglas y endpoints."""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ganaderia import db as ganaderia_db
from app.nucleo.opciones import DIAS_ALERTA, ESTADOS_ANIMAL, ESTADOS_REPRODUCTIVOS, SEXOS_ANIMAL, TIPOS_EVENTO
from app.nucleo.tipos import FechaOpcional, IdOpcional, opcion
from app.nucleo.utilidades import normalizar_texto

router = APIRouter(tags=["Ganadería"])


class CaravanaRepetida(Exception):
    """Ya hay otro animal con esa caravana: se pide confirmación antes de guardar."""

    def __init__(self, existentes):
        self.existentes = existentes
        descripcion = ", ".join(f"{a['especie']} ({a['categoria'].lower()})" for a in existentes)
        super().__init__(
            f"Ya hay {'un animal' if len(existentes) == 1 else f'{len(existentes)} animales'} con la caravana "
            f"'{existentes[0]['caravana']}': {descripcion}. ¿Querés guardarlo igual?"
        )


# ---------- Modelos ----------

class EspecieDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=40)
    dias_gestacion: int | None = Field(default=None, gt=0, le=800)  # Vacío = sin preñez (aves).


class CategoriaDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=40)
    sexo: opcion(SEXOS_ANIMAL) = ""


class AnimalDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    caravana: str = Field(min_length=1, max_length=60)  # Caravana, o nombre del grupo.
    categoria_id: int  # La categoría ya dice de qué especie es.
    es_grupo: bool = False
    cantidad: int = Field(default=1, ge=0, le=1_000_000)  # Solo para grupos.
    raza: str = Field(default="", max_length=60)
    rodeo: str = Field(default="", max_length=60)  # Lote, potrero o grupo.
    fecha_nacimiento: FechaOpcional = None
    estado_reproductivo: opcion(ESTADOS_REPRODUCTIVOS) = ""
    fecha_probable_parto: FechaOpcional = None
    madre_id: IdOpcional = None
    estado: opcion(ESTADOS_ANIMAL) = "activo"
    observaciones: str = Field(default="", max_length=1000)
    # La caravana se puede repetir, pero hay que confirmarlo (así no se repite por error).
    confirmar_repetida: bool = False


class EventoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date = Field(default_factory=date.today)
    tipo: opcion(TIPOS_EVENTO)
    resultado: Literal["", "prenada", "vacia"] = ""  # Solo para tacto.
    crias_machos: int = Field(default=0, ge=0, le=20)  # Solo para parto (cerdas: camadas grandes).
    crias_hembras: int = Field(default=0, ge=0, le=20)
    detalle: str = Field(default="", max_length=500)
    fecha_probable_parto: FechaOpcional = None  # Opcional en un tacto positivo.

    @field_validator("resultado", mode="before")
    @classmethod
    def normalizar_resultado(cls, valor):
        """"Preñada" -> "prenada" (normalizar_texto saca tildes y la ñ)."""
        return normalizar_texto(valor) if isinstance(valor, str) else valor


# ---------- Reglas compartidas ----------

def animales_por_caravana(caravana: str, especie_id=None, excluir_id=None):
    """Todos los animales con esa caravana exacta (sin importar mayúsculas ni tildes)."""
    buscada = normalizar_texto(caravana)
    return [
        a for a in ganaderia_db.listar_animales(incluir_bajas=True)
        if a["id"] != excluir_id and normalizar_texto(a["caravana"]) == buscada
        and (especie_id is None or a["especie_id"] == especie_id)
    ]


def _revisar_caravana(datos: AnimalDatos, excluir_id=None):
    if datos.confirmar_repetida:
        return
    existentes = animales_por_caravana(datos.caravana, excluir_id=excluir_id)
    if existentes:
        raise CaravanaRepetida(existentes)


def partos_para_alertar():
    return ganaderia_db.partos_proximos(date.today() + timedelta(days=DIAS_ALERTA))


# ---------- Endpoints: especies y categorías ----------

@router.get("/especies")
def ver_especies():
    return ganaderia_db.listar_especies()


@router.post("/especies", status_code=201)
def crear_especie(datos: EspecieDatos):
    return ganaderia_db.agregar_especie(datos.nombre, datos.dias_gestacion)


@router.put("/especies/{especie_id}")
def editar_especie(especie_id: int, datos: EspecieDatos):
    return ganaderia_db.editar_especie(especie_id, datos.nombre, datos.dias_gestacion)


@router.delete("/especies/{especie_id}", status_code=204)
def eliminar_especie(especie_id: int):
    ganaderia_db.eliminar_especie(especie_id)


@router.post("/especies/{especie_id}/categorias", status_code=201)
def crear_categoria(especie_id: int, datos: CategoriaDatos):
    return ganaderia_db.agregar_categoria(especie_id, datos.nombre, datos.sexo)


@router.put("/categorias-animal/{categoria_id}")
def editar_categoria(categoria_id: int, datos: CategoriaDatos):
    return ganaderia_db.editar_categoria(categoria_id, datos.nombre, datos.sexo)


@router.delete("/categorias-animal/{categoria_id}", status_code=204)
def eliminar_categoria(categoria_id: int):
    ganaderia_db.eliminar_categoria(categoria_id)


# ---------- Endpoints: animales ----------

@router.get("/animales")
def ver_animales(incluir_bajas: bool = False):
    return ganaderia_db.listar_animales(incluir_bajas)


@router.post("/animales", status_code=201)
def crear_animal(datos: AnimalDatos):
    _revisar_caravana(datos)
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
    _revisar_caravana(datos, animal_id)
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


@router.get("/nacimientos")
def ver_nacimientos():
    """Partos y abortos de todas las especies: la web arma con esto el resumen de crías."""
    return ganaderia_db.listar_nacimientos()


@router.delete("/eventos-animales/{evento_id}", status_code=204)
def eliminar_evento(evento_id: int):
    ganaderia_db.eliminar_evento(evento_id)
