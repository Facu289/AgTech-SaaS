"""Órdenes de trabajo: modelo, reglas y endpoints de la API (web/ordenes.html y web/orden.html)."""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.insumos import db as insumos_db
from app.lotes import db as lotes_db
from app.nucleo.opciones import TAREAS_ORDEN
from app.nucleo.tipos import EnteroOpcional, FechaOpcional, IdOpcional, Numero, NumeroOpcional, opcion
from app.nucleo.utilidades import formatear_cantidad, normalizar_texto
from app.ordenes import db as ordenes_db

router = APIRouter(tags=["Órdenes de trabajo"])


# ---------- Modelos ----------

class LoteDeOrden(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lote: str = Field(min_length=1, max_length=80)  # Como en la planilla: "31+32", "44N", "1 al 12"
    hectareas: Numero = Field(gt=0)


class ProductoDeOrden(BaseModel):
    insumo_id: int
    cantidad_total: Numero = Field(gt=0)  # Lo que sale del stock. La dosis/ha = total / ha de la orden.


class OrdenDatos(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    numero: str = Field(default="", max_length=30)  # "1-033": solo para identificarla.
    campania_id: IdOpcional = None
    campo: str = Field(default="", max_length=80)
    tarea: opcion(TAREAS_ORDEN)
    maquina: str = Field(default="", max_length=80)
    operarios: str = Field(default="", max_length=300)  # Separados por coma.
    fecha_emision: date = Field(default_factory=date.today)
    estado_lote: str = Field(default="", max_length=80)  # Como en la planilla (ej: "Maíz").
    cultivo: str = Field(default="", max_length=80)
    caldo_ha: NumeroOpcional = None    # Litros de caldo por hectárea.
    tancadas: EnteroOpcional = Field(default=None, ge=1, le=10000)
    descripcion: str = Field(default="", max_length=2000)  # La franja amarilla: indicaciones.
    lotes: list[LoteDeOrden] = Field(default=[], max_length=200)
    productos: list[ProductoDeOrden] = Field(default=[], max_length=50)


class Realizar(BaseModel):
    fecha_realizacion: FechaOpcional = None  # Vacía = hoy.


# ---------- Desarmar "1 al 12" en lotes ----------
# En la planilla, una fila de lotes puede ser "31+32", "1 al 12" o "44N".
# Para el registro de cada lote hay que saber cuáles son: 31 y 32; 1, 2, 3... 12; 44N.

RANGO = re.compile(r"^\s*(\d+)\s*(?:al|a|hasta)\s*(\d+)\s*$", re.IGNORECASE)
MAXIMO_RANGO = 300


def desarmar_lotes(texto: str):
    """'31+32' → ['31', '32'] | '1 al 12' → ['1', ..., '12'] | '44N' → ['44N']."""
    nombres = []
    for parte in re.split(r"[+,;/]| y ", texto):
        parte = parte.strip()
        if not parte:
            continue
        rango = RANGO.match(parte)
        if rango and int(rango.group(1)) <= int(rango.group(2)) and int(rango.group(2)) - int(rango.group(1)) < MAXIMO_RANGO:
            nombres += [str(n) for n in range(int(rango.group(1)), int(rango.group(2)) + 1)]
        else:
            nombres.append(parte)
    return list(dict.fromkeys(nombres))  # Sin repetidos, en el mismo orden.


def _clave_lote(nombre: str):
    """'Lote 5' y '5' son el mismo lote."""
    clave = normalizar_texto(nombre)
    return clave[5:].strip() if clave.startswith("lote ") else clave


def _buscar_lote(nombre, campo, lotes_mapa):
    """El lote del mapa con ese nombre en el campo de la orden.

    Si la orden no dice el campo, sirve solo si hay UN lote con ese nombre (si hay un "1" en
    cada campo, no se puede saber cuál es: queda sin vincular).
    """
    candidatos = [l for l in lotes_mapa if _clave_lote(l["nombre"]) == _clave_lote(nombre)]
    if campo:
        candidatos = [l for l in candidatos if normalizar_texto(l["campo"]) == normalizar_texto(campo)]
    return candidatos[0] if len(candidatos) == 1 else None


def lotes_de_la_orden(orden, lotes_mapa=None):
    """Cada lote de la orden, buscado en el mapa (por campo + nombre). Devuelve (vinculados, sin_vincular).

    vinculados: [{"lote_id", "nombre", "campo", "hectareas"}] (las ha son las del lote en el mapa).
    sin_vincular: nombres que no están en el mapa (o están sin hectáreas): se avisan.
    """
    if lotes_mapa is None:
        lotes_mapa = lotes_db.listar_lotes(incluir_archivados=True)
    vinculados, sin_vincular, vistos = [], [], set()
    for fila in orden["lotes"]:
        for nombre in desarmar_lotes(fila["lote"]):
            lote = _buscar_lote(nombre, orden["campo"], lotes_mapa)
            if lote is None or not lote["hectareas"]:
                sin_vincular.append(nombre)
            elif lote["id"] not in vistos:
                vistos.add(lote["id"])
                vinculados.append({"lote_id": lote["id"], "nombre": lote["nombre"], "campo": lote["campo"],
                                   "hectareas": lote["hectareas"]})
    return vinculados, sin_vincular


# ---------- Reglas ----------

def _con_calculos(orden, lotes_mapa=None):
    """Agrega lo que se calcula: dosis/ha de cada producto, advertencias de stock y lotes del mapa."""
    hectareas = orden["hectareas"] or 0
    for producto in orden["productos"]:
        producto["dosis_ha"] = producto["cantidad_total"] / hectareas if hectareas else None
        producto["por_tancada"] = producto["cantidad_total"] / orden["tancadas"] if orden["tancadas"] else None
    orden["advertencias"] = []
    if orden["estado"] == "pendiente":
        for falta in ordenes_db.faltantes(orden):
            if falta["archivado"]:
                texto = f"{falta['insumo']} está archivado: reactivalo en el stock o cambiá el producto."
            else:
                texto = (f"Falta {falta['insumo']}: hay {formatear_cantidad(falta['hay'])} {falta['unidad']} y la orden "
                         f"usa {formatear_cantidad(falta['necesita'])}. Modificá la orden o no hagas la aplicación.")
            orden["advertencias"].append(texto)
    orden["lotes_mapa"], orden["lotes_sin_vincular"] = lotes_de_la_orden(orden, lotes_mapa)
    return orden


def _revisar_productos(datos: OrdenDatos):
    """Los productos tienen que existir en el stock (para poder descontarlos)."""
    for producto in datos.productos:
        if insumos_db.obtener_insumo(producto.insumo_id) is None:
            raise HTTPException(status_code=400, detail="Uno de los productos ya no existe en el stock.")


def _datos(datos: OrdenDatos) -> dict:
    valores = datos.model_dump(mode="json")  # Las fechas pasan a texto "AAAA-MM-DD".
    return valores


# ---------- Endpoints ----------

@router.get("/ordenes")
def ver_ordenes(estado: Optional[str] = None, campania_id: Optional[int] = None):
    lotes_mapa = lotes_db.listar_lotes(incluir_archivados=True)
    return [_con_calculos(o, lotes_mapa) for o in ordenes_db.listar_ordenes(estado, campania_id)]


@router.get("/ordenes/siguiente-numero")
def ver_siguiente_numero():
    return {"numero": ordenes_db.siguiente_numero()}


@router.get("/ordenes/{orden_id}")
def ver_orden(orden_id: int):
    orden = _con_calculos(ordenes_db.obtener_orden(orden_id))
    orden["movimientos"] = insumos_db.movimientos_de_orden(orden_id)
    return orden


@router.post("/ordenes", status_code=201)
def crear_orden(datos: OrdenDatos):
    _revisar_productos(datos)
    return _con_calculos(ordenes_db.agregar_orden(_datos(datos)))


@router.put("/ordenes/{orden_id}")
def editar_orden(orden_id: int, datos: OrdenDatos):
    _revisar_productos(datos)
    return _con_calculos(ordenes_db.editar_orden(orden_id, _datos(datos)))


@router.post("/ordenes/{orden_id}/realizar")
def realizar_orden(orden_id: int, datos: Realizar):
    fecha = datos.fecha_realizacion or date.today()
    try:
        return _con_calculos(ordenes_db.realizar_orden(orden_id, fecha))
    except ordenes_db.FaltaStock as error:
        detalle = "; ".join(
            f"{f['insumo']} (archivado)" if f["archivado"]
            else f"{f['insumo']}: hay {formatear_cantidad(f['hay'])} {f['unidad']}, hacen falta {formatear_cantidad(f['necesita'])}"
            for f in error.faltantes
        )
        return JSONResponse(status_code=409, content={
            "detail": f"No alcanza el stock, no se descontó nada. {detalle}. Cargá la entrada que falta o modificá la orden.",
        })


@router.post("/ordenes/{orden_id}/pendiente")
def volver_a_pendiente(orden_id: int):
    return _con_calculos(ordenes_db.volver_a_pendiente(orden_id))


@router.post("/ordenes/{orden_id}/anular")
def anular_orden(orden_id: int):
    return _con_calculos(ordenes_db.anular_orden(orden_id, True))


@router.post("/ordenes/{orden_id}/reactivar")
def reactivar_orden(orden_id: int):
    return _con_calculos(ordenes_db.anular_orden(orden_id, False))


@router.delete("/ordenes/{orden_id}", status_code=204)
def eliminar_orden(orden_id: int):
    ordenes_db.eliminar_orden(orden_id)


@router.get("/lotes/{lote_id}/aplicaciones")
def ver_aplicaciones_del_lote(lote_id: int):
    """El registro del lote: cada orden (no anulada) que lo incluye, con lo que le tocó a ESE lote.

    Dosis/ha = la de la orden (total / ha de la orden). Cantidad del lote = dosis × ha del lote.
    """
    lote = lotes_db.obtener_lote(lote_id)
    lotes_mapa = lotes_db.listar_lotes(incluir_archivados=True)
    aplicaciones = []
    for orden in ordenes_db.listar_ordenes():
        if orden["estado"] == "anulada":
            continue
        vinculados, _ = lotes_de_la_orden(orden, lotes_mapa)
        if not any(v["lote_id"] == lote_id for v in vinculados):
            continue
        _con_calculos(orden, lotes_mapa)
        productos = [
            {"insumo": p["insumo"], "unidad": p["unidad"], "dosis_ha": p["dosis_ha"],
             "cantidad": p["dosis_ha"] * lote["hectareas"] if p["dosis_ha"] is not None else None}
            for p in orden["productos"]
        ]
        aplicaciones.append({
            "orden_id": orden["id"], "numero": orden["numero"], "tarea": orden["tarea"], "estado": orden["estado"],
            "fecha": orden["fecha_realizacion"] or orden["fecha_emision"], "campania": orden["campania"],
            "hectareas": lote["hectareas"], "productos": productos,
        })
    return aplicaciones
