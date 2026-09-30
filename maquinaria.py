"""Maquinaria: modelos, endpoints de la API y comandos de Telegram."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import database
import db_maquinaria
from opciones import (
    DIAS_ALERTA, MEDIDAS_SERVICE, RUBROS_CONTACTO, TIPOS_MANTENIMIENTO, TIPOS_MAQUINA, TIPOS_TRABAJO,
    TIPOS_VENCIMIENTO,
)
from tipos import EnteroOpcional, FechaOpcional, IdOpcional, Numero, NumeroOCero, NumeroOpcional, opcion
from utilidades import (
    describir_dias, dias_hasta, elegir_uno, formatear_cantidad, formatear_fecha, leer_cantidad,
    leer_numero, normalizar_texto, separar_motivo,
)

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
    for m in db_maquinaria.listar_maquinas(incluir_archivadas=True):
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
    return db_maquinaria.vencimientos_proximos(date.today() + timedelta(days=DIAS_ALERTA))


# ---------- Endpoints: máquinas ----------

@router.get("/maquinas")
def ver_maquinas(incluir_archivadas: bool = False):
    """Lista de máquinas. Cada una trae su service programado más urgente (o None)."""
    maquinas = db_maquinaria.listar_maquinas(incluir_archivadas)
    mas_urgente = {}
    for plan in db_maquinaria.listar_planes():  # Ya vienen del más urgente al menos urgente.
        mas_urgente.setdefault(plan["maquina_id"], plan)
    for maquina in maquinas:
        maquina["proximo_service"] = mas_urgente.get(maquina["id"])
    return maquinas


@router.post("/maquinas", status_code=201)
def crear_maquina(datos: MaquinaDatos):
    _revisar_nombre(datos.nombre)
    return db_maquinaria.agregar_maquina(_datos_maquina(datos))


@router.get("/maquinas/{maquina_id}")
def ver_ficha_maquina(maquina_id: int):
    """Todo lo de una máquina: datos, services, trabajos, vencimientos y repuestos."""
    maquina = db_maquinaria.obtener_maquina(maquina_id)
    if maquina is None:
        raise db_maquinaria.MaquinaNoEncontrada()
    return {
        "maquina": maquina,
        "mantenimientos": db_maquinaria.listar_mantenimientos(maquina_id),
        "planes": db_maquinaria.listar_planes(maquina_id, solo_activos=False),
        "trabajos": db_maquinaria.listar_trabajos(maquina_id=maquina_id),
        "vencimientos": db_maquinaria.listar_vencimientos(incluir_resueltos=True, maquina_id=maquina_id),
        "repuestos": [
            i for i in database.listar_insumos(incluir_archivados=False) if i["maquina_id"] == maquina_id
        ],
    }


@router.put("/maquinas/{maquina_id}")
def editar_maquina(maquina_id: int, datos: MaquinaDatos):
    _revisar_nombre(datos.nombre, maquina_id)
    return db_maquinaria.editar_maquina(maquina_id, _datos_maquina(datos))


@router.post("/maquinas/{maquina_id}/horas")
def actualizar_horas(maquina_id: int, datos: Horas):
    return db_maquinaria.actualizar_horas(maquina_id, datos.horas_motor, datos.horas_trilla)


@router.post("/maquinas/{maquina_id}/archivar")
def archivar_maquina(maquina_id: int):
    return db_maquinaria.archivar_maquina(maquina_id, True)


@router.post("/maquinas/{maquina_id}/desarchivar")
def desarchivar_maquina(maquina_id: int):
    return db_maquinaria.archivar_maquina(maquina_id, False)


@router.delete("/maquinas/{maquina_id}", status_code=204)
def eliminar_maquina(maquina_id: int):
    db_maquinaria.eliminar_maquina(maquina_id)


# ---------- Endpoints: services, trabajos ----------

@router.post("/maquinas/{maquina_id}/mantenimientos", status_code=201)
def crear_mantenimiento(maquina_id: int, datos: MantenimientoNuevo):
    return db_maquinaria.agregar_mantenimiento(
        maquina_id, datos.fecha, datos.tipo, datos.descripcion, datos.horas, datos.costo, datos.planes
    )


@router.delete("/mantenimientos/{mantenimiento_id}", status_code=204)
def eliminar_mantenimiento(mantenimiento_id: int):
    db_maquinaria.eliminar_mantenimiento(mantenimiento_id)


@router.post("/maquinas/{maquina_id}/trabajos", status_code=201)
def crear_trabajo(maquina_id: int, datos: TrabajoNuevo):
    return db_maquinaria.agregar_trabajo(
        maquina_id, datos.fecha, datos.tipo, datos.hectareas, datos.lote, datos.cultivo, datos.observaciones
    )


@router.get("/trabajos")
def ver_trabajos(maquina_id: Optional[int] = None, tipo: Optional[str] = None,
                 desde: Optional[date] = None, hasta: Optional[date] = None):
    return db_maquinaria.listar_trabajos(maquina_id, desde, hasta, tipo)


@router.delete("/trabajos/{trabajo_id}", status_code=204)
def eliminar_trabajo(trabajo_id: int):
    db_maquinaria.eliminar_trabajo(trabajo_id)


# ---------- Endpoints: service programado ----------

def _revisar_plan_nuevo(datos: PlanDatos, maquina_id):
    maquina = db_maquinaria.obtener_maquina(maquina_id)
    if maquina is None:
        raise db_maquinaria.MaquinaNoEncontrada()
    if datos.medida == "trilla" and maquina["tipo"] != "cosechadora":
        raise HTTPException(status_code=400, detail="Las horas de trilla son solo para cosechadoras")
    for plan in db_maquinaria.listar_planes(maquina_id, solo_activos=False):
        if normalizar_texto(plan["nombre"]) == normalizar_texto(datos.nombre):
            raise HTTPException(status_code=409, detail=f"Esta máquina ya tiene un plan '{plan['nombre']}'")


@router.get("/services")
def ver_services():
    """Todos los planes activos (de máquinas no archivadas), del más urgente al menos urgente."""
    return db_maquinaria.listar_planes()


@router.post("/maquinas/{maquina_id}/planes", status_code=201)
def crear_plan(maquina_id: int, datos: PlanDatos):
    _revisar_plan_nuevo(datos, maquina_id)
    return db_maquinaria.agregar_plan(
        maquina_id, datos.nombre, datos.cada_horas, datos.medida, datos.ultima_horas, datos.ultima_fecha, datos.activo
    )


@router.put("/planes/{plan_id}")
def editar_plan(plan_id: int, datos: PlanDatos):
    actual = next((p for p in db_maquinaria.listar_planes(solo_activos=False) if p["id"] == plan_id), None)
    if actual is None:
        raise database.NoEncontrado("No existe ese plan de service.")
    otros = [p for p in db_maquinaria.listar_planes(actual["maquina_id"], solo_activos=False) if p["id"] != plan_id]
    if any(normalizar_texto(p["nombre"]) == normalizar_texto(datos.nombre) for p in otros):
        raise HTTPException(status_code=409, detail="Esta máquina ya tiene un plan con ese nombre")
    return db_maquinaria.editar_plan(
        plan_id, datos.nombre, datos.cada_horas, datos.medida, datos.ultima_horas, datos.ultima_fecha, datos.activo
    )


@router.delete("/planes/{plan_id}", status_code=204)
def eliminar_plan(plan_id: int):
    db_maquinaria.eliminar_plan(plan_id)


# ---------- Endpoints: vencimientos ----------

@router.get("/vencimientos")
def ver_vencimientos(incluir_resueltos: bool = False):
    return db_maquinaria.listar_vencimientos(incluir_resueltos)


@router.post("/vencimientos", status_code=201)
def crear_vencimiento(datos: VencimientoDatos):
    return db_maquinaria.agregar_vencimiento(
        datos.descripcion, datos.tipo, datos.fecha_vencimiento, datos.maquina_id, datos.observaciones
    )


@router.put("/vencimientos/{vencimiento_id}")
def editar_vencimiento(vencimiento_id: int, datos: VencimientoDatos):
    return db_maquinaria.editar_vencimiento(
        vencimiento_id, datos.descripcion, datos.tipo, datos.fecha_vencimiento,
        datos.maquina_id, datos.observaciones, datos.resuelto,
    )


@router.delete("/vencimientos/{vencimiento_id}", status_code=204)
def eliminar_vencimiento(vencimiento_id: int):
    db_maquinaria.eliminar_vencimiento(vencimiento_id)


# ---------- Endpoints: contactos ----------

@router.get("/contactos")
def ver_contactos():
    return db_maquinaria.listar_contactos()


@router.post("/contactos", status_code=201)
def crear_contacto(datos: ContactoDatos):
    return db_maquinaria.agregar_contacto(datos.model_dump())


@router.put("/contactos/{contacto_id}")
def editar_contacto(contacto_id: int, datos: ContactoDatos):
    return db_maquinaria.editar_contacto(contacto_id, datos.model_dump())


@router.delete("/contactos/{contacto_id}", status_code=204)
def eliminar_contacto(contacto_id: int):
    db_maquinaria.eliminar_contacto(contacto_id)


# ---------- Telegram ----------

def _horas(valor) -> str:
    return f"{formatear_cantidad(valor)} h"


def _elegir_maquina(texto: str):
    return elegir_uno(db_maquinaria.listar_maquinas(), texto, "máquina")


def _linea_vencimiento(v) -> str:
    dias = dias_hasta(v["fecha_vencimiento"])
    icono = "🔴" if dias < 0 else "🟡"
    maquina = f" ({v['maquina_nombre']})" if v.get("maquina_nombre") else ""
    cuando = "venció " + describir_dias(dias) if dias < 0 else "vence " + describir_dias(dias)
    return f"{icono} {v['descripcion']}{maquina}: {cuando} ({formatear_fecha(v['fecha_vencimiento'])})"


ICONOS_ESTADO_SERVICE = {"vencido": "🔴", "proximo": "🟡", "ok": "🟢"}


def _describir_plan(plan) -> str:
    faltan = plan["faltan"]
    if faltan < 0:
        cuando = f"pasado por {_horas(-faltan)}"
    else:
        cuando = f"faltan {_horas(faltan)}"
    trilla = " de trilla" if plan["medida"] == "trilla" else ""
    return (f"{ICONOS_ESTADO_SERVICE[plan['estado']]} {plan['nombre']} (cada {_horas(plan['cada_horas'])}{trilla}): "
            f"{cuando}, toca a las {_horas(plan['proximo'])}")


def comando_services(argumento: str) -> str:
    """/services [máquina]  ->  service programado: qué toca y cuánto falta."""
    planes = db_maquinaria.listar_planes()
    if argumento:
        buscado = normalizar_texto(argumento)
        planes = [p for p in planes if buscado in normalizar_texto(p["maquina_nombre"])]
    if not planes:
        return ("No hay services programados" + (f" para '{argumento}'." if argumento else ".") +
                "\nSe cargan desde la web, en la ficha de cada máquina.")
    lineas = ["🔧 Service programado"]
    maquina_actual = None
    for plan in sorted(planes, key=lambda p: (p["maquina_nombre"], p["faltan"])):
        if plan["maquina_nombre"] != maquina_actual:
            maquina_actual = plan["maquina_nombre"]
            lineas.append(f"\n{maquina_actual} ({_horas(plan['horas_motor'])})")
        lineas.append("  " + _describir_plan(plan))
    return "\n".join(lineas)


def comando_maquinas(argumento: str) -> str:
    """/maquinas [filtro]  ->  lista con horas y último service."""
    maquinas = db_maquinaria.listar_maquinas()
    if argumento:
        buscado = normalizar_texto(argumento)
        maquinas = [
            m for m in maquinas
            if buscado.rstrip("s") == m["tipo"] or buscado in normalizar_texto(
                f"{m['nombre']} {m['marca']} {m['modelo']} {m['patente']}")
        ]
    if not maquinas:
        return f"No encontré máquinas con '{argumento}'." if argumento else (
            "No hay máquinas cargadas. Cargalas desde la web: Maquinaria → Listado.")

    lineas = ["🚜 Maquinaria"]
    for m in maquinas:
        linea = f"\n• {m['nombre']} ({TIPOS_MAQUINA.get(m['tipo'], m['tipo']).lower()})\n  Horas: {_horas(m['horas_motor'])}"
        if m["horas_trilla"] is not None:
            linea += f" · trilla {_horas(m['horas_trilla'])}"
        if m["ultimo_service"]:
            linea += f"\n  Último service: {formatear_fecha(m['ultimo_service'])}"
            if m["horas_ultimo_service"] is not None:
                desde = m["horas_motor"] - m["horas_ultimo_service"]
                linea += f" ({_horas(m['horas_ultimo_service'])}, hace {_horas(desde)})"
        planes = [p for p in db_maquinaria.listar_planes(m["id"])]
        if planes:
            linea += "\n  Próximo: " + _describir_plan(planes[0])
        lineas.append(linea)

    vencimientos = vencimientos_para_alertar()
    if vencimientos:
        lineas.append("\n📅 Vencimientos próximos")
        lineas += [_linea_vencimiento(v) for v in vencimientos]
    return "\n".join(lineas)


def comando_horas(argumento: str) -> str:
    """/horas <máquina> <horas>  ->  actualiza el horómetro."""
    uso = "Formato: /horas <máquina> <horas>\nEjemplo: /horas jd 6110 1520"
    partes = argumento.rsplit(maxsplit=1)
    if len(partes) < 2:
        return uso
    horas = leer_numero(partes[1])
    if horas is None:
        return f"'{partes[1]}' no es un número de horas.\n{uso}"
    maquina, error = _elegir_maquina(partes[0])
    if error:
        return error
    if horas < maquina["horas_motor"]:
        return (
            f"⚠️ {_horas(horas)} es menos de lo que tiene cargado {maquina['nombre']} "
            f"({_horas(maquina['horas_motor'])}). Si es una corrección, hacela desde la web."
        )
    db_maquinaria.actualizar_horas(maquina["id"], horas_motor=horas)
    return f"✅ {maquina['nombre']}: {_horas(horas)} (antes {_horas(maquina['horas_motor'])})."


def comando_trabajo(argumento: str) -> str:
    """/trabajo <máquina> <hectáreas> <tipo> [- lote]"""
    tipos = ", ".join(TIPOS_TRABAJO)
    uso = (
        "Formato: /trabajo <máquina> <hectáreas> <tipo> - <lote opcional>\n"
        "Ejemplo: /trabajo cosechadora 120 trilla - lote 4\n"
        f"Tipos: {tipos}"
    )
    principal, lote = separar_motivo(argumento)
    palabras = principal.split()
    if len(palabras) < 3:
        return uso
    tipo = normalizar_texto(palabras[-1])
    if tipo not in TIPOS_TRABAJO:
        return f"'{palabras[-1]}' no es un tipo de trabajo.\n{uso}"
    hectareas = leer_cantidad(palabras[-2])
    if hectareas is None:
        return f"'{palabras[-2]}' no es una cantidad de hectáreas.\n{uso}"
    maquina, error = _elegir_maquina(" ".join(palabras[:-2]))
    if error:
        return error
    db_maquinaria.agregar_trabajo(maquina["id"], date.today(), tipo, hectareas, lote)
    lote_texto = f" en {lote}" if lote else ""
    return f"✅ {TIPOS_TRABAJO[tipo]} registrada: {formatear_cantidad(hectareas)} ha{lote_texto} con {maquina['nombre']}."


def _planes_mencionados(planes, descripcion: str):
    """Qué planes nombra la descripción. "todo"/"completo" = todos los planes."""
    texto = normalizar_texto(descripcion)
    if texto in ("todo", "todos", "completo", "service completo"):
        return planes
    return [p for p in planes if normalizar_texto(p["nombre"]) in texto or (texto and texto in normalizar_texto(p["nombre"]))]


def comando_mantenimiento(tipo: str, argumento: str) -> str:
    """/service <máquina> [- descripción]  |  /arreglo <máquina> - descripción

    Si la descripción nombra un plan de service programado ("aceite", "filtros"),
    ese plan queda hecho y su contador vuelve a empezar.
    """
    uso = (
        f"Formato: /{tipo} <máquina> - <descripción>\n"
        f"Ejemplo: /{tipo} jd 6110 - cambio de aceite y filtros"
    )
    nombre, descripcion = separar_motivo(argumento)
    if not nombre:
        return uso
    if tipo == "arreglo" and not descripcion:
        return "Contá qué se arregló después de ' - '.\n" + uso
    maquina, error = _elegir_maquina(nombre)
    if error:
        return error

    planes = db_maquinaria.listar_planes(maquina["id"]) if tipo == "service" else []
    hechos = _planes_mencionados(planes, descripcion) if descripcion else []
    db_maquinaria.agregar_mantenimiento(
        maquina["id"], date.today(), tipo, descripcion or "Service", maquina["horas_motor"],
        plan_ids=[p["id"] for p in hechos],
    )
    respuesta = (
        f"✅ {TIPOS_MANTENIMIENTO[tipo]} registrado en {maquina['nombre']} "
        f"a las {_horas(maquina['horas_motor'])}: {descripcion or 'Service'}"
    )
    if hechos:
        respuesta += "\n🔧 Plan reiniciado: " + ", ".join(p["nombre"] for p in hechos)
    elif planes:
        nombres = ", ".join(p["nombre"] for p in planes)
        respuesta += f"\n(No marqué ningún plan. Si fue uno de estos, nombralo: {nombres}. O poné '- todo'.)"
    return respuesta + "\n(Si las horas no están al día, primero usá /horas)"


def comando_vencimientos(argumento: str) -> str:
    """/vencimientos  ->  los que vencen en los próximos 30 días y los ya vencidos."""
    vencimientos = vencimientos_para_alertar()
    if not vencimientos:
        return f"📅 No hay vencimientos en los próximos {DIAS_ALERTA} días. 👌"
    return "📅 Vencimientos próximos\n" + "\n".join(_linea_vencimiento(v) for v in vencimientos)
