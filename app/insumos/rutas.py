"""Insumos y movimientos: modelos de datos, reglas y endpoints de la API."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.insumos import db as insumos_db
from app.maquinaria import db as maquinaria_db
from app.nucleo.opciones import CATEGORIAS, UNIDADES, subcategorias_de
from app.nucleo.tipos import IdOpcional, NumeroOCero, opcion
from app.nucleo.utilidades import formatear_cantidad, leer_cantidad, normalizar_texto

router = APIRouter(tags=["Insumos"])

Categoria = opcion(CATEGORIAS)
Unidad = opcion(UNIDADES)


# ---------- Modelos ----------

class InsumoDatos(BaseModel):
    """Los datos de un insumo que se pueden cargar o editar."""
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    categoria: Categoria
    subcategoria: str = ""
    unidad: Unidad
    stock_minimo: NumeroOCero = 0
    maquina_id: IdOpcional = None  # Solo para repuestos: para qué máquina es.

    @field_validator("subcategoria", mode="before")
    @classmethod
    def normalizar_subcategoria(cls, valor):
        return normalizar_texto(valor) if isinstance(valor, str) else (valor or "")

    @model_validator(mode="after")
    def revisar_subcategoria(self):
        """La subcategoría tiene que corresponder a la categoría (herbicida -> agroquímico)."""
        validas = subcategorias_de(self.categoria)
        if self.subcategoria and self.subcategoria not in validas:
            raise ValueError(f"'{self.subcategoria}' no es una subcategoría de {self.categoria}")
        if self.categoria != "repuesto":
            self.maquina_id = None
        return self


class InsumoNuevo(InsumoDatos):
    """Para crear: además se puede cargar un stock inicial."""
    cantidad: NumeroOCero = 0


class Insumo(BaseModel):
    """Un insumo guardado, tal como lo devuelve la API."""
    id: int
    nombre: str
    categoria: str
    subcategoria: str
    unidad: str
    cantidad: float
    stock_minimo: float
    maquina_id: Optional[int]
    maquina_nombre: Optional[str]
    archivado: bool
    tiene_movimientos: bool


class MovimientoNuevo(BaseModel):
    """Lo que hay que mandar para registrar una entrada o salida."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: Literal["entrada", "salida"]
    cantidad: float = Field(gt=0, allow_inf_nan=False)  # Sin "infinito".
    motivo: str = Field(default="", max_length=200)

    @field_validator("cantidad", mode="before")
    @classmethod
    def convertir_cantidad(cls, valor):
        """Si la cantidad llega como texto ("2,5", "1.500"), la interpreta
        igual que en Telegram. Si llega como número (20, 2.5), la deja pasar."""
        if not isinstance(valor, str):
            return valor
        cantidad = leer_cantidad(valor)
        if cantidad is None:
            raise ValueError("cantidad inválida (usá, por ejemplo, 20 o 2,5)")
        return cantidad


class Movimiento(BaseModel):
    id: int
    insumo_id: int
    tipo: str
    cantidad: float
    motivo: str
    fecha: str


class MovimientoConInsumo(Movimiento):
    insumo_nombre: str
    categoria: str
    unidad: str


# ---------- Reglas compartidas (API y Telegram) ----------

def insumo_con_mismo_nombre(nombre: str, excluir_id=None):
    """Devuelve el insumo que ya se llama igual (sin importar tildes ni mayúsculas), o None.

    La base ya impide "Urea" y "UREA" (NOCASE), pero no "Ruleman" y "Rulemán".
    Incluye los archivados (el nombre sigue ocupado aunque esté archivado).
    """
    buscado = normalizar_texto(nombre)
    for existente in insumos_db.listar_insumos(incluir_archivados=True):
        if existente["id"] != excluir_id and normalizar_texto(existente["nombre"]) == buscado:
            return existente
    return None


def mensaje_duplicado(existente) -> str:
    texto = f"Ya existe un insumo llamado '{existente['nombre']}'"
    if existente["archivado"]:
        texto += " (está archivado: podés desarchivarlo desde la web)"
    return texto


def stock_bajo(insumo) -> bool:
    """True si tiene stock mínimo definido y está en o por debajo."""
    return insumo["stock_minimo"] > 0 and insumo["cantidad"] <= insumo["stock_minimo"]


def insumos_con_stock_bajo():
    return [i for i in insumos_db.listar_insumos() if stock_bajo(i)]


def _revisar_datos(datos: InsumoDatos, excluir_id=None):
    """Chequeos que necesitan la base: nombre repetido y máquina existente."""
    existente = insumo_con_mismo_nombre(datos.nombre, excluir_id)
    if existente:
        raise HTTPException(status_code=409, detail=mensaje_duplicado(existente))
    if datos.maquina_id is not None and maquinaria_db.obtener_maquina(datos.maquina_id) is None:
        raise HTTPException(status_code=400, detail="La máquina elegida no existe")


# ---------- Endpoints ----------

@router.get("/insumos", response_model=list[Insumo])
def ver_insumos(incluir_archivados: bool = False):
    return insumos_db.listar_insumos(incluir_archivados)


@router.post("/insumos", response_model=Insumo, status_code=201)
def crear_insumo(insumo: InsumoNuevo):
    _revisar_datos(insumo)
    return insumos_db.agregar_insumo(
        insumo.nombre, insumo.categoria, insumo.unidad, insumo.cantidad,
        insumo.subcategoria, insumo.maquina_id, insumo.stock_minimo,
    )


@router.put("/insumos/{insumo_id}", response_model=Insumo)
def editar_insumo(insumo_id: int, datos: InsumoDatos):
    """Edita los datos. La cantidad NO se edita acá: se cambia con movimientos."""
    _revisar_datos(datos, excluir_id=insumo_id)
    return insumos_db.editar_insumo(
        insumo_id, datos.nombre, datos.categoria, datos.subcategoria,
        datos.unidad, datos.maquina_id, datos.stock_minimo,
    )


@router.post("/insumos/{insumo_id}/archivar", response_model=Insumo)
def archivar_insumo(insumo_id: int):
    return insumos_db.archivar_insumo(insumo_id, True)


@router.post("/insumos/{insumo_id}/desarchivar", response_model=Insumo)
def desarchivar_insumo(insumo_id: int):
    return insumos_db.archivar_insumo(insumo_id, False)


@router.delete("/insumos/{insumo_id}", status_code=204)
def eliminar_insumo(insumo_id: int):
    """Solo se puede eliminar si nunca tuvo movimientos; si no, hay que archivarlo."""
    insumos_db.eliminar_insumo(insumo_id)


@router.post("/insumos/{insumo_id}/movimientos", response_model=Insumo, status_code=201)
def crear_movimiento(insumo_id: int, movimiento: MovimientoNuevo):
    """Registra una entrada o salida y devuelve el insumo con el stock actualizado."""
    try:
        return insumos_db.registrar_movimiento(
            insumo_id, movimiento.tipo, movimiento.cantidad, movimiento.motivo
        )
    except insumos_db.StockInsuficiente as error:
        insumo = insumos_db.obtener_insumo(insumo_id)
        raise HTTPException(
            status_code=400,
            detail=f"No alcanza el stock de {insumo['nombre']}: hay "
                   f"{formatear_cantidad(error.disponible)} {insumo['unidad']}",
        )


@router.get("/insumos/{insumo_id}/movimientos", response_model=list[Movimiento])
def ver_movimientos(insumo_id: int):
    return insumos_db.listar_movimientos(insumo_id)


@router.get("/movimientos", response_model=list[MovimientoConInsumo])
def buscar_movimientos(
    insumo_id: Optional[int] = None,
    tipo: Optional[Literal["entrada", "salida"]] = None,
    categoria: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    texto: Optional[str] = None,
    limite: int = Query(default=500, ge=1, le=5000),
):
    """Historial de movimientos de todos los insumos, con filtros opcionales."""
    return insumos_db.buscar_movimientos(insumo_id, tipo, categoria, desde, hasta, texto, limite)
