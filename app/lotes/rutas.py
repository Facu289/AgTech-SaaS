"""Lotes, cultivos y campañas: modelos, reglas y endpoints de la API.

Los usan las páginas web/lotes.html, web/lote.html (ficha), web/cultivos.html y el mapa de Inicio.
"""
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.lotes import db as lotes_db
from app.lotes import geometria
from app.nucleo.tipos import FechaOpcional, NumeroOpcional
from app.nucleo.utilidades import normalizar_texto

router = APIRouter(tags=["Lotes"])


# ---------- Modelo ----------

class LoteDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=80)  # Ej: "La Loma", "Lote 4"
    geometria: Optional[dict[str, Any]] = None        # Polígono GeoJSON (vacío = lote sin dibujar).
    hectareas: NumeroOpcional = None                  # Vacío = las calcula la app con el dibujo.
    observaciones: str = Field(default="", max_length=1000)

    @field_validator("geometria")
    @classmethod
    def _revisar_geometria(cls, valor):
        # Si el polígono no es válido, ValueError → Pydantic responde 422 con el mensaje.
        return None if valor is None else geometria.validar_poligono(valor)


class CultivoDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=40)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")  # Como lo da <input type="color">: "#16A34A".


class CampaniaDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=20)  # Ej: "2026/27"


class LoteCultivoDatos(BaseModel):
    """Qué se sembró en un lote en una campaña."""
    model_config = ConfigDict(str_strip_whitespace=True)

    campania_id: int
    cultivo_id: int
    ciclo: Literal["primera", "segunda"] = "primera"
    variedad: str = Field(default="", max_length=80)  # Variedad o híbrido.
    fecha_siembra: FechaOpcional = None
    fecha_cosecha: FechaOpcional = None
    hectareas: NumeroOpcional = None  # Vacío = todo el lote.
    rinde: NumeroOpcional = None      # Quintales por hectárea (qq/ha).
    observaciones: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _fechas_en_orden(self):
        if self.fecha_siembra and self.fecha_cosecha and self.fecha_cosecha < self.fecha_siembra:
            raise ValueError("la cosecha no puede ser antes de la siembra")
        return self


# ---------- Reglas ----------

def _revisar_nombre(nombre, excluir_id=None):
    """Dos lotes no pueden llamarse igual (sin importar mayúsculas ni tildes)."""
    buscado = normalizar_texto(nombre)
    for lote in lotes_db.listar_lotes(incluir_archivados=True):
        if lote["id"] != excluir_id and normalizar_texto(lote["nombre"]) == buscado:
            extra = " (está archivado)" if lote["archivado"] else ""
            raise HTTPException(status_code=409, detail=f"Ya existe un lote llamado '{lote['nombre']}'{extra}")


def _revisar_nombre_en(listado, nombre, que, excluir_id=None):
    """Para cultivos y campañas: "Maiz" y "Maíz" son el mismo nombre."""
    buscado = normalizar_texto(nombre)
    for fila in listado:
        if fila["id"] != excluir_id and normalizar_texto(fila["nombre"]) == buscado:
            raise HTTPException(status_code=409, detail=f"Ya existe {que} '{fila['nombre']}'")


def _revisar_ciclo_libre(lote_id, datos: LoteCultivoDatos, excluir_id=None):
    """Un lote tiene UN cultivo de primera y UNO de segunda por campaña."""
    for fila in lotes_db.listar_lote_cultivos(lote_id=lote_id, campania_id=datos.campania_id):
        if fila["id"] != excluir_id and fila["ciclo"] == datos.ciclo:
            raise HTTPException(
                status_code=409,
                detail=f"Este lote ya tiene {fila['cultivo']} de {datos.ciclo} en la campaña {fila['campania']}: editalo.",
            )


def _datos_lote(datos: LoteDatos) -> dict:
    """Si no escribiste las hectáreas, se usan las del dibujo."""
    valores = datos.model_dump()
    if valores["hectareas"] is None and valores["geometria"] is not None:
        valores["hectareas"] = geometria.hectareas(valores["geometria"])
    return valores


def _con_calculo(lote: dict) -> dict:
    """Agrega las hectáreas que da el dibujo, para comparar con las guardadas (pueden ser a mano)."""
    lote["hectareas_calculadas"] = geometria.hectareas(lote["geometria"]) if lote["geometria"] else None
    return lote


# ---------- Endpoints ----------

@router.get("/lotes")
def ver_lotes(incluir_archivados: bool = False, campania_id: Optional[int] = None):
    """Los lotes. Con campania_id, cada uno trae además sus cultivos de esa campaña (para pintar el mapa)."""
    lotes = [_con_calculo(lote) for lote in lotes_db.listar_lotes(incluir_archivados)]
    por_lote = {}
    if campania_id is not None:
        for fila in lotes_db.listar_lote_cultivos(campania_id=campania_id):
            por_lote.setdefault(fila["lote_id"], []).append(fila)
    for lote in lotes:
        lote["cultivos"] = por_lote.get(lote["id"], [])
    return lotes


@router.get("/lotes/{lote_id}")
def ver_lote(lote_id: int):
    """La ficha: el lote y todos sus cultivos, de la campaña más nueva a la más vieja."""
    lote = _con_calculo(lotes_db.obtener_lote(lote_id))
    lote["historial"] = lotes_db.listar_lote_cultivos(lote_id=lote_id)
    return lote


@router.post("/lotes", status_code=201)
def crear_lote(datos: LoteDatos):
    _revisar_nombre(datos.nombre)
    return _con_calculo(lotes_db.agregar_lote(_datos_lote(datos)))


@router.put("/lotes/{lote_id}")
def editar_lote(lote_id: int, datos: LoteDatos):
    lotes_db.obtener_lote(lote_id)  # 404 si no existe (antes de revisar el nombre).
    _revisar_nombre(datos.nombre, lote_id)
    return _con_calculo(lotes_db.editar_lote(lote_id, _datos_lote(datos)))


@router.post("/lotes/{lote_id}/archivar")
def archivar_lote(lote_id: int):
    return _con_calculo(lotes_db.archivar_lote(lote_id, True))


@router.post("/lotes/{lote_id}/desarchivar")
def desarchivar_lote(lote_id: int):
    return _con_calculo(lotes_db.archivar_lote(lote_id, False))


@router.delete("/lotes/{lote_id}", status_code=204)
def eliminar_lote(lote_id: int):
    lotes_db.eliminar_lote(lote_id)


# ---------- Endpoints: cultivos ----------

@router.get("/cultivos")
def ver_cultivos():
    return lotes_db.listar_cultivos()


@router.post("/cultivos", status_code=201)
def crear_cultivo(datos: CultivoDatos):
    _revisar_nombre_en(lotes_db.listar_cultivos(), datos.nombre, "un cultivo llamado")
    return lotes_db.agregar_cultivo(datos.nombre, datos.color.upper())


@router.put("/cultivos/{cultivo_id}")
def editar_cultivo(cultivo_id: int, datos: CultivoDatos):
    _revisar_nombre_en(lotes_db.listar_cultivos(), datos.nombre, "un cultivo llamado", cultivo_id)
    return lotes_db.editar_cultivo(cultivo_id, datos.nombre, datos.color.upper())


@router.delete("/cultivos/{cultivo_id}", status_code=204)
def eliminar_cultivo(cultivo_id: int):
    lotes_db.eliminar_cultivo(cultivo_id)


# ---------- Endpoints: campañas ----------

@router.get("/campanias")
def ver_campanias():
    return lotes_db.listar_campanias()


@router.post("/campanias", status_code=201)
def crear_campania(datos: CampaniaDatos):
    _revisar_nombre_en(lotes_db.listar_campanias(), datos.nombre, "la campaña")
    return lotes_db.agregar_campania(datos.nombre)


@router.put("/campanias/{campania_id}")
def editar_campania(campania_id: int, datos: CampaniaDatos):
    _revisar_nombre_en(lotes_db.listar_campanias(), datos.nombre, "la campaña", campania_id)
    return lotes_db.editar_campania(campania_id, datos.nombre)


@router.delete("/campanias/{campania_id}", status_code=204)
def eliminar_campania(campania_id: int):
    lotes_db.eliminar_campania(campania_id)


# ---------- Endpoints: cultivo de cada lote ----------

@router.get("/lote-cultivos")
def ver_lote_cultivos(campania_id: Optional[int] = None):
    """Todos los cultivos de todos los lotes (o de una campaña): para resúmenes y el Excel."""
    return lotes_db.listar_lote_cultivos(campania_id=campania_id)


@router.post("/lotes/{lote_id}/cultivos", status_code=201)
def agregar_cultivo_al_lote(lote_id: int, datos: LoteCultivoDatos):
    lotes_db.obtener_lote(lote_id)  # 404 si no existe.
    _revisar_ciclo_libre(lote_id, datos)
    # mode="json": las fechas pasan a texto "AAAA-MM-DD", como se guardan en toda la base.
    return lotes_db.agregar_lote_cultivo(lote_id, datos.model_dump(mode="json"))


@router.put("/lote-cultivos/{fila_id}")
def editar_cultivo_del_lote(fila_id: int, datos: LoteCultivoDatos):
    actual = next((f for f in lotes_db.listar_lote_cultivos() if f["id"] == fila_id), None)
    if actual is None:
        raise lotes_db.NoEncontrado("No existe ese cultivo del lote (puede que ya se haya borrado).")
    _revisar_ciclo_libre(actual["lote_id"], datos, fila_id)
    return lotes_db.editar_lote_cultivo(fila_id, datos.model_dump(mode="json"))


@router.delete("/lote-cultivos/{fila_id}", status_code=204)
def eliminar_cultivo_del_lote(fila_id: int):
    lotes_db.eliminar_lote_cultivo(fila_id)
