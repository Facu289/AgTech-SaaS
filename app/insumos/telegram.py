"""Comandos de Telegram de stock: /stock, /repuestos, /nuevo, /entrada, /salida."""
from app.insumos import db as insumos_db
from app.insumos.rutas import insumo_con_mismo_nombre, mensaje_duplicado, stock_bajo
from app.nucleo.opciones import CATEGORIAS, SUBCATEGORIAS, UNIDADES, categoria_de_subcategoria, subcategorias_de
from app.nucleo.utilidades import (
    buscar_por_nombre, formatear_cantidad, leer_cantidad, nombres_parecidos, normalizar_texto, separar_motivo,
)


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
    return _texto_lista(insumos_db.listar_insumos(), "📋 Stock de insumos", argumento)


def comando_repuestos(argumento: str) -> str:
    """/repuestos [filtro]  ->  solo repuestos: /repuestos filtros | /repuestos jd"""
    repuestos = [i for i in insumos_db.listar_insumos() if i["categoria"] == "repuesto"]
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

    insumo = insumos_db.agregar_insumo(nombre, categoria, unidad, 0, subcategoria)
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

    insumos = insumos_db.listar_insumos()
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
        actualizado = insumos_db.registrar_movimiento(insumo["id"], tipo, cantidad, motivo)
    except insumos_db.StockInsuficiente as error:
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
