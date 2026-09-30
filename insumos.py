"""Insumos, movimientos de stock y notas: modelos, endpoints de la API y comandos de Telegram."""
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import database
import db_maquinaria
from opciones import CATEGORIAS, SUBCATEGORIAS, UNIDADES, categoria_de_subcategoria, subcategorias_de
from tipos import IdOpcional, NumeroOCero, opcion
from utilidades import (
    buscar_por_nombre, formatear_cantidad, leer_cantidad, nombres_parecidos,
    normalizar_texto, separar_motivo,
)

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
    for existente in database.listar_insumos(incluir_archivados=True):
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
    return [i for i in database.listar_insumos() if stock_bajo(i)]


def _revisar_datos(datos: InsumoDatos, excluir_id=None):
    """Chequeos que necesitan la base: nombre repetido y máquina existente."""
    existente = insumo_con_mismo_nombre(datos.nombre, excluir_id)
    if existente:
        raise HTTPException(status_code=409, detail=mensaje_duplicado(existente))
    if datos.maquina_id is not None and db_maquinaria.obtener_maquina(datos.maquina_id) is None:
        raise HTTPException(status_code=400, detail="La máquina elegida no existe")


# ---------- Endpoints ----------

@router.get("/insumos", response_model=list[Insumo])
def ver_insumos(incluir_archivados: bool = False):
    return database.listar_insumos(incluir_archivados)


@router.post("/insumos", response_model=Insumo, status_code=201)
def crear_insumo(insumo: InsumoNuevo):
    _revisar_datos(insumo)
    return database.agregar_insumo(
        insumo.nombre, insumo.categoria, insumo.unidad, insumo.cantidad,
        insumo.subcategoria, insumo.maquina_id, insumo.stock_minimo,
    )


@router.put("/insumos/{insumo_id}", response_model=Insumo)
def editar_insumo(insumo_id: int, datos: InsumoDatos):
    """Edita los datos. La cantidad NO se edita acá: se cambia con movimientos."""
    _revisar_datos(datos, excluir_id=insumo_id)
    return database.editar_insumo(
        insumo_id, datos.nombre, datos.categoria, datos.subcategoria,
        datos.unidad, datos.maquina_id, datos.stock_minimo,
    )


@router.post("/insumos/{insumo_id}/archivar", response_model=Insumo)
def archivar_insumo(insumo_id: int):
    return database.archivar_insumo(insumo_id, True)


@router.post("/insumos/{insumo_id}/desarchivar", response_model=Insumo)
def desarchivar_insumo(insumo_id: int):
    return database.archivar_insumo(insumo_id, False)


@router.delete("/insumos/{insumo_id}", status_code=204)
def eliminar_insumo(insumo_id: int):
    """Solo se puede eliminar si nunca tuvo movimientos; si no, hay que archivarlo."""
    database.eliminar_insumo(insumo_id)


@router.post("/insumos/{insumo_id}/movimientos", response_model=Insumo, status_code=201)
def crear_movimiento(insumo_id: int, movimiento: MovimientoNuevo):
    """Registra una entrada o salida y devuelve el insumo con el stock actualizado."""
    try:
        return database.registrar_movimiento(
            insumo_id, movimiento.tipo, movimiento.cantidad, movimiento.motivo
        )
    except database.StockInsuficiente as error:
        insumo = database.obtener_insumo(insumo_id)
        raise HTTPException(
            status_code=400,
            detail=f"No alcanza el stock de {insumo['nombre']}: hay "
                   f"{formatear_cantidad(error.disponible)} {insumo['unidad']}",
        )


@router.get("/insumos/{insumo_id}/movimientos", response_model=list[Movimiento])
def ver_movimientos(insumo_id: int):
    return database.listar_movimientos(insumo_id)


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
    return database.buscar_movimientos(insumo_id, tipo, categoria, desde, hasta, texto, limite)


# ---------- Telegram ----------

EMOJIS_CATEGORIA = {
    "agroquimico": "🧪", "semilla": "🌱", "fertilizante": "🧂", "combustible": "⛽",
    "repuesto": "🔧", "balanceado": "🌾", "medicamento": "💉", "otro": "📦",
}


def _nombre_subcategoria(insumo) -> str:
    return subcategorias_de(insumo["categoria"]).get(insumo["subcategoria"], "")


def _coincide(insumo, filtro: str) -> bool:
    """¿El insumo coincide con el filtro? Por categoría, subcategoría o parte del nombre.

    Acepta plurales: "herbicidas" -> "herbicida", "agroquimicos" -> "agroquimico".
    """
    for palabra in (filtro, filtro.rstrip("s")):
        if palabra in (insumo["categoria"], insumo["subcategoria"]):
            return True
    return filtro in normalizar_texto(insumo["nombre"])


def _linea_insumo(insumo) -> str:
    cantidad = formatear_cantidad(insumo["cantidad"])
    sub = _nombre_subcategoria(insumo)
    texto = f"  • {insumo['nombre']}"
    if sub:
        texto += f" ({sub.lower()})"
    texto += f": {cantidad} {insumo['unidad']}"
    if insumo.get("maquina_nombre"):
        texto += f" → {insumo['maquina_nombre']}"
    if stock_bajo(insumo):
        texto += " ⚠️ bajo mínimo"
    return texto


def _texto_lista(insumos, titulo: str, filtro: str) -> str:
    if filtro:
        buscado = normalizar_texto(filtro)
        insumos = [i for i in insumos if _coincide(i, buscado)]
        titulo += f" · filtro: {filtro}"
    if not insumos:
        return f"No encontré insumos con '{filtro}'." if filtro else "No hay insumos cargados todavía."

    lineas = [titulo]
    categoria_actual = None
    for insumo in insumos:  # Ya vienen ordenados por categoría.
        if insumo["categoria"] != categoria_actual:
            categoria_actual = insumo["categoria"]
            emoji = EMOJIS_CATEGORIA.get(categoria_actual, "📦")
            lineas.append(f"\n{emoji} {CATEGORIAS.get(categoria_actual, categoria_actual)}")
        lineas.append(_linea_insumo(insumo))
    return "\n".join(lineas)


def comando_stock(argumento: str) -> str:
    """/stock [filtro]  ->  todo el stock, o filtrado: /stock herbicida | /stock semillas | /stock urea"""
    return _texto_lista(database.listar_insumos(), "📋 Stock de insumos", argumento)


def comando_repuestos(argumento: str) -> str:
    """/repuestos [filtro]  ->  solo repuestos: /repuestos filtros | /repuestos jd"""
    repuestos = [i for i in database.listar_insumos() if i["categoria"] == "repuesto"]
    if argumento:
        buscado = normalizar_texto(argumento)
        repuestos = [
            r for r in repuestos
            if _coincide(r, buscado) or buscado in normalizar_texto(r.get("maquina_nombre") or "")
        ]
        if not repuestos:
            return f"No encontré repuestos con '{argumento}'."
    return _texto_lista(repuestos, "🔧 Repuestos", "")


def ayuda_nuevo() -> str:
    subs = ", ".join(s for subcats in SUBCATEGORIAS.values() for s in subcats)
    return (
        "Formato: /nuevo <nombre> <categoría> <unidad>\n"
        "Ejemplo: /nuevo urea fertilizante kg\n"
        "En vez de la categoría podés poner el tipo:\n"
        "/nuevo glifosato herbicida litros\n\n"
        f"Categorías: {', '.join(CATEGORIAS)}\n"
        f"Tipos: {subs}\n"
        f"Unidades: {', '.join(UNIDADES)}"
    )


def comando_nuevo(argumento: str) -> str:
    """Crea un insumo. Formato: /nuevo <nombre> <categoría o tipo> <unidad>"""
    palabras = argumento.split()
    if len(palabras) < 3:
        return ayuda_nuevo()

    # Las dos últimas palabras son categoría (o subcategoría) y unidad; el resto es el nombre.
    # Así el nombre puede tener espacios: "/nuevo Rulemán 6205 rodamientos unidades".
    nombre = " ".join(palabras[:-2])
    clase = normalizar_texto(palabras[-2])
    unidad = normalizar_texto(palabras[-1])

    if clase in CATEGORIAS:
        categoria, subcategoria = clase, ""
    elif categoria_de_subcategoria(clase):
        categoria, subcategoria = categoria_de_subcategoria(clase), clase
    else:
        return f"'{palabras[-2]}' no es una categoría válida.\n\n{ayuda_nuevo()}"
    if unidad not in UNIDADES:
        return f"'{palabras[-1]}' no es una unidad válida.\n\n{ayuda_nuevo()}"
    if len(nombre) > 100:
        return "El nombre es demasiado largo (máximo 100 caracteres)."

    # Evita duplicados que solo difieren en tildes: "Ruleman" vs "Rulemán".
    existente = insumo_con_mismo_nombre(nombre)
    if existente:
        return mensaje_duplicado(existente) + "."

    insumo = database.agregar_insumo(nombre, categoria, unidad, 0, subcategoria)
    detalle = f"{categoria}, {subcategoria}" if subcategoria else categoria
    return (
        f"✅ Insumo creado: {insumo['nombre']} ({detalle}, {unidad}). Stock: 0\n"
        f"Ahora podés cargarle stock: /entrada <cantidad> {insumo['nombre']}"
    )


def mensaje_insumo_inexistente(nombre: str, insumos) -> str:
    """Arma el aviso de 'no existe', con parecidos y cómo crearlo."""
    lineas = [f"❌ El insumo '{nombre}' no existe."]
    parecidos = nombres_parecidos(insumos, nombre)
    if parecidos:
        lineas.append("¿Quisiste decir: " + ", ".join(parecidos) + "?")
    titulo = "Si es un insumo nuevo, crealo con:" if parecidos else "Para crearlo:"
    lineas.append(
        f"\n{titulo}\n/nuevo {nombre} <categoría> <unidad>\n"
        f"Ejemplo: /nuevo {nombre} fertilizante kg"
    )
    return "\n".join(lineas)


def comando_movimiento(tipo: str, argumento: str) -> str:
    """Maneja /entrada y /salida. Formato: <cantidad> <insumo> [- motivo]"""
    uso = (
        f"Formato: /{tipo} <cantidad> <insumo> - <motivo opcional>\n"
        f"Ejemplo: /{tipo} 20 urea - compra"
    )
    partes = argumento.split(maxsplit=1)
    if len(partes) < 2:
        return uso

    cantidad = leer_cantidad(partes[0])
    if cantidad is None:
        return f"Primero va la cantidad: '{partes[0]}' no es un número.\n{uso}"

    # "urea - compra" -> nombre="urea", motivo="compra"
    nombre, motivo = separar_motivo(partes[1], "Telegram")
    if not nombre:
        return uso

    insumos = database.listar_insumos()
    encontrados = buscar_por_nombre(insumos, nombre)

    # Si no encontró nada y hay un guion sin espacios ("urea-remanente"),
    # probamos cortando en cada guion, de derecha a izquierda:
    # "urea-remanente" -> nombre "urea", motivo "remanente".
    # (Así "2,4-D" sigue funcionando: primero se busca el nombre completo).
    resto = nombre
    while not encontrados and "-" in resto:
        resto, _, _ = resto.rpartition("-")
        if resto.strip():
            encontrados = buscar_por_nombre(insumos, resto)
            if encontrados:
                motivo_extra = nombre[len(resto) + 1:].strip()
                nombre = resto.strip()
                if motivo == "Telegram" and motivo_extra:
                    motivo = motivo_extra

    if not encontrados:
        return mensaje_insumo_inexistente(nombre, insumos)
    if len(encontrados) > 1:
        opciones = "\n".join(f"  • {i['nombre']}" for i in encontrados)
        return f"Encontré varios insumos con '{nombre}':\n{opciones}\nEscribí el nombre más completo."

    insumo = encontrados[0]
    try:
        actualizado = database.registrar_movimiento(insumo["id"], tipo, cantidad, motivo)
    except database.StockInsuficiente as error:
        disponible = formatear_cantidad(error.disponible)
        return f"⚠️ No alcanza el stock de {insumo['nombre']}: hay {disponible} {insumo['unidad']}."

    signo = "+" if tipo == "entrada" else "-"
    respuesta = (
        f"✅ {tipo.capitalize()} registrada: {signo}{formatear_cantidad(cantidad)} "
        f"{insumo['unidad']} de {insumo['nombre']} ({motivo})\n"
        f"Stock actual: {formatear_cantidad(actualizado['cantidad'])} {insumo['unidad']}"
    )
    if stock_bajo(actualizado):
        respuesta += f"\n⚠️ Quedó por debajo del mínimo ({formatear_cantidad(actualizado['stock_minimo'])})."
    return respuesta


# ---------- Notas (Telegram) ----------

def comando_nota(argumento: str) -> str:
    if not argumento:
        return "Escribí la nota después del comando.\nEjemplo: /nota comprar 20 bolsas de urea"
    nota_id = database.agregar_nota(argumento)
    return f"📝 Nota #{nota_id} guardada."


def comando_notas(argumento: str) -> str:
    notas = database.listar_notas_pendientes()
    if not notas:
        return "No hay notas pendientes. 🎉"
    lineas = ["📝 Notas pendientes"]
    for nota in notas:
        fecha = datetime.strptime(nota["creada_en"], "%Y-%m-%d %H:%M:%S")
        lineas.append(f"#{nota['id']} ({fecha:%d/%m %H:%M}) {nota['texto']}")
    lineas.append("\nPara cerrar una: /hecha <número>")
    return "\n".join(lineas)


def comando_hecha(argumento: str) -> str:
    if not argumento.isdigit():
        return "Indicá el número de la nota.\nEjemplo: /hecha 3"
    nota_id = int(argumento)
    if database.marcar_nota_hecha(nota_id):
        return f"✅ Nota #{nota_id} marcada como hecha."
    return f"No encontré una nota pendiente con el número {nota_id}."
