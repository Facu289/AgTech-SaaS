"""Maquinaria: modelos de datos, reglas y endpoints de la API."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.insumos import db as insumos_db
from app.maquinaria import db as maquinaria_db
from app.nucleo import database
from app.nucleo.opciones import (
    DIAS_ALERTA, MEDIDAS_SERVICE, RUBROS_CONTACTO, TIPOS_MANTENIMIENTO, TIPOS_MAQUINA, TIPOS_TRABAJO,
    TIPOS_VENCIMIENTO,
)
from app.nucleo.tipos import EnteroOpcional, FechaOpcional, IdOpcional, Numero, NumeroOCero, NumeroOpcional, opcion
from app.nucleo.utilidades import normalizar_texto

router = APIRouter(tags=["Maquinaria"])


# ---------- Modelos ----------

class MaquinaDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=60)  # Cómo la llamás: "Tractor JD 6110"
    tipo: opcion(TIPOS_MAQUINA)
    marca: str = Field(default="", max_length=60)
    modelo: str = Field(default="", max_length=60)
    anio: EnteroOpcional = Field(default=None, ge=1900, le=2100)
    numero_serie: str = Field(default="", max_length=60)
    serie_monitor: str = Field(default="", max_length=60)  # Monitor GPS / piloto: para licencias y suscripciones.
    patente: str = Field(default="", max_length=20)
    horas_motor: NumeroOCero = 0
    horas_trilla: NumeroOpcional = None  # Solo cosechadoras.
    observaciones: str = Field(default="", max_length=1000)


class MantenimientoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date = Field(default_factory=date.today)
    tipo: opcion(TIPOS_MANTENIMIENTO) = "service"
    horas: NumeroOpcional = None
    descripcion: str = Field(min_length=1, max_length=1000)
    costo: NumeroOpcional = None
    planes: list[int] = []  # Planes de service programado que este service deja hechos.


class TrabajoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fecha: date = Field(default_factory=date.today)
    tipo: opcion(TIPOS_TRABAJO)
    hectareas: Numero = Field(gt=0)
    lote: str = Field(default="", max_length=100)
    cultivo: str = Field(default="", max_length=60)
    observaciones: str = Field(default="", max_length=500)


class VencimientoDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    descripcion: str = Field(min_length=1, max_length=200)
    tipo: opcion(TIPOS_VENCIMIENTO)
    fecha_vencimiento: date
    maquina_id: IdOpcional = None
    observaciones: str = Field(default="", max_length=500)
    resuelto: bool = False


class PlanDatos(BaseModel):
    """Un plan de service programado: "hacer <nombre> cada <cada_horas> horas"."""
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=80)  # Ej: "Cambio de aceite"
    cada_horas: Numero = Field(gt=0)
    medida: opcion(MEDIDAS_SERVICE) = "motor"
    ultima_horas: NumeroOpcional = None  # Vacío = se hizo ahora (horas actuales).
    ultima_fecha: FechaOpcional = None
    activo: bool = True


class Horas(BaseModel):
    """Para actualizar solo el horómetro desde la web (se permite corregir hacia abajo)."""
    horas_motor: Numero
    horas_trilla: NumeroOpcional = None


class ContactoDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    rubro: opcion(RUBROS_CONTACTO)
    empresa: str = Field(default="", max_length=100)
    telefono: str = Field(default="", max_length=50)
    email: str = Field(default="", max_length=100)
    notas: str = Field(default="", max_length=1000)


# ---------- Reglas compartidas ----------

def maquina_con_mismo_nombre(nombre: str, excluir_id=None):
    buscado = normalizar_texto(nombre)
    for m in maquinaria_db.listar_maquinas(incluir_archivadas=True):
        if m["id"] != excluir_id and normalizar_texto(m["nombre"]) == buscado:
            return m
    return None


def _revisar_nombre(nombre, excluir_id=None):
    existente = maquina_con_mismo_nombre(nombre, excluir_id)
    if existente:
        extra = " (está archivada)" if existente["archivado"] else ""
        raise HTTPException(status_code=409, detail=f"Ya existe una máquina llamada '{existente['nombre']}'{extra}")


def _datos_maquina(datos: MaquinaDatos) -> dict:
    valores = datos.model_dump()
    if valores["tipo"] != "cosechadora":
        valores["horas_trilla"] = None
    return valores


def vencimientos_para_alertar():
    """Vencimientos sin resolver en los próximos DIAS_ALERTA días (o ya vencidos)."""
    return maquinaria_db.vencimientos_proximos(date.today() + timedelta(days=DIAS_ALERTA))


# ---------- Endpoints: máquinas ----------

@router.get("/maquinas")
def ver_maquinas(incluir_archivadas: bool = False):
    """Lista de máquinas. Cada una trae su service programado más urgente (o None)."""
    maquinas = maquinaria_db.listar_maquinas(incluir_archivadas)
    mas_urgente = {}
    for plan in maquinaria_db.listar_planes():  # Ya vienen del más urgente al menos urgente.
        mas_urgente.setdefault(plan["maquina_id"], plan)
    for maquina in maquinas:
        maquina["proximo_service"] = mas_urgente.get(maquina["id"])
    return maquinas


@router.post("/maquinas", status_code=201)
def crear_maquina(datos: MaquinaDatos):
    _revisar_nombre(datos.nombre)
    return maquinaria_db.agregar_maquina(_datos_maquina(datos))


@router.get("/maquinas/{maquina_id}")
def ver_ficha_maquina(maquina_id: int):
    """Todo lo de una máquina: datos, services, trabajos, vencimientos y repuestos."""
    maquina = maquinaria_db.obtener_maquina(maquina_id)
    if maquina is None:
        raise maquinaria_db.MaquinaNoEncontrada()
    return {
        "maquina": maquina,
        "mantenimientos": maquinaria_db.listar_mantenimientos(maquina_id),
        "planes": maquinaria_db.listar_planes(maquina_id, solo_activos=False),
        "trabajos": maquinaria_db.listar_trabajos(maquina_id=maquina_id),
        "vencimientos": maquinaria_db.listar_vencimientos(incluir_resueltos=True, maquina_id=maquina_id),
        "repuestos": insumos_db.listar_repuestos_de_maquina(maquina_id),
    }


@router.put("/maquinas/{maquina_id}")
def editar_maquina(maquina_id: int, datos: MaquinaDatos):
    _revisar_nombre(datos.nombre, maquina_id)
    return maquinaria_db.editar_maquina(maquina_id, _datos_maquina(datos))


@router.post("/maquinas/{maquina_id}/horas")
def actualizar_horas(maquina_id: int, datos: Horas):
    return maquinaria_db.actualizar_horas(maquina_id, datos.horas_motor, datos.horas_trilla)


@router.post("/maquinas/{maquina_id}/archivar")
def archivar_maquina(maquina_id: int):
    return maquinaria_db.archivar_maquina(maquina_id, True)


@router.post("/maquinas/{maquina_id}/desarchivar")
def desarchivar_maquina(maquina_id: int):
    return maquinaria_db.archivar_maquina(maquina_id, False)


@router.delete("/maquinas/{maquina_id}", status_code=204)
def eliminar_maquina(maquina_id: int):
    maquinaria_db.eliminar_maquina(maquina_id)


# ---------- Endpoints: services, trabajos ----------

@router.post("/maquinas/{maquina_id}/mantenimientos", status_code=201)
def crear_mantenimiento(maquina_id: int, datos: MantenimientoNuevo):
    return maquinaria_db.agregar_mantenimiento(
        maquina_id, datos.fecha, datos.tipo, datos.descripcion, datos.horas, datos.costo, datos.planes
    )


@router.delete("/mantenimientos/{mantenimiento_id}", status_code=204)
def eliminar_mantenimiento(mantenimiento_id: int):
    maquinaria_db.eliminar_mantenimiento(mantenimiento_id)


@router.post("/maquinas/{maquina_id}/trabajos", status_code=201)
def crear_trabajo(maquina_id: int, datos: TrabajoNuevo):
    return maquinaria_db.agregar_trabajo(
        maquina_id, datos.fecha, datos.tipo, datos.hectareas, datos.lote, datos.cultivo, datos.observaciones
    )


@router.get("/trabajos")
def ver_trabajos(maquina_id: Optional[int] = None, tipo: Optional[str] = None,
                 desde: Optional[date] = None, hasta: Optional[date] = None):
    return maquinaria_db.listar_trabajos(maquina_id, desde, hasta, tipo)


@router.delete("/trabajos/{trabajo_id}", status_code=204)
def eliminar_trabajo(trabajo_id: int):
    maquinaria_db.eliminar_trabajo(trabajo_id)


# ---------- Endpoints: service programado ----------

def _revisar_plan_nuevo(datos: PlanDatos, maquina_id):
    maquina = maquinaria_db.obtener_maquina(maquina_id)
    if maquina is None:
        raise maquinaria_db.MaquinaNoEncontrada()
    if datos.medida == "trilla" and maquina["tipo"] != "cosechadora":
        raise HTTPException(status_code=400, detail="Las horas de trilla son solo para cosechadoras")
    for plan in maquinaria_db.listar_planes(maquina_id, solo_activos=False):
        if normalizar_texto(plan["nombre"]) == normalizar_texto(datos.nombre):
            raise HTTPException(status_code=409, detail=f"Esta máquina ya tiene un plan '{plan['nombre']}'")


@router.get("/services")
def ver_services():
    """Todos los planes activos (de máquinas no archivadas), del más urgente al menos urgente."""
    return maquinaria_db.listar_planes()


@router.post("/maquinas/{maquina_id}/planes", status_code=201)
def crear_plan(maquina_id: int, datos: PlanDatos):
    _revisar_plan_nuevo(datos, maquina_id)
    return maquinaria_db.agregar_plan(
        maquina_id, datos.nombre, datos.cada_horas, datos.medida, datos.ultima_horas, datos.ultima_fecha, datos.activo
    )


@router.put("/planes/{plan_id}")
def editar_plan(plan_id: int, datos: PlanDatos):
    actual = next((p for p in maquinaria_db.listar_planes(solo_activos=False) if p["id"] == plan_id), None)
    if actual is None:
        raise database.NoEncontrado("No existe ese plan de service.")
    otros = [p for p in maquinaria_db.listar_planes(actual["maquina_id"], solo_activos=False) if p["id"] != plan_id]
    if any(normalizar_texto(p["nombre"]) == normalizar_texto(datos.nombre) for p in otros):
        raise HTTPException(status_code=409, detail="Esta máquina ya tiene un plan con ese nombre")
    return maquinaria_db.editar_plan(
        plan_id, datos.nombre, datos.cada_horas, datos.medida, datos.ultima_horas, datos.ultima_fecha, datos.activo
    )


@router.delete("/planes/{plan_id}", status_code=204)
def eliminar_plan(plan_id: int):
    maquinaria_db.eliminar_plan(plan_id)


# ---------- Endpoints: vencimientos ----------

@router.get("/vencimientos")
def ver_vencimientos(incluir_resueltos: bool = False):
    return maquinaria_db.listar_vencimientos(incluir_resueltos)


@router.post("/vencimientos", status_code=201)
def crear_vencimiento(datos: VencimientoDatos):
    return maquinaria_db.agregar_vencimiento(
        datos.descripcion, datos.tipo, datos.fecha_vencimiento, datos.maquina_id, datos.observaciones
    )


@router.put("/vencimientos/{vencimiento_id}")
def editar_vencimiento(vencimiento_id: int, datos: VencimientoDatos):
    return maquinaria_db.editar_vencimiento(
        vencimiento_id, datos.descripcion, datos.tipo, datos.fecha_vencimiento,
        datos.maquina_id, datos.observaciones, datos.resuelto,
    )


@router.delete("/vencimientos/{vencimiento_id}", status_code=204)
def eliminar_vencimiento(vencimiento_id: int):
    maquinaria_db.eliminar_vencimiento(vencimiento_id)


# ---------- Endpoints: contactos ----------

@router.get("/contactos")
def ver_contactos():
    return maquinaria_db.listar_contactos()


@router.post("/contactos", status_code=201)
def crear_contacto(datos: ContactoDatos):
    return maquinaria_db.agregar_contacto(datos.model_dump())


@router.put("/contactos/{contacto_id}")
def editar_contacto(contacto_id: int, datos: ContactoDatos):
    return maquinaria_db.editar_contacto(contacto_id, datos.model_dump())


@router.delete("/contactos/{contacto_id}", status_code=204)
def eliminar_contacto(contacto_id: int):
    maquinaria_db.eliminar_contacto(contacto_id)
