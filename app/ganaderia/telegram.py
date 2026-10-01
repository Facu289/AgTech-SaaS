"""Comandos de Telegram de animales: /animales, /animal, /parto, /aborto, /tacto, /servicio.

La caravana se puede repetir entre animales (ej: la vaca 12 y la oveja 12). Si hay más
de uno, el bot pregunta y se aclara poniendo la especie antes: /animal ovino 12
"""
from collections import Counter, defaultdict
from datetime import date

from app.ganaderia import db as ganaderia_db
from app.ganaderia.rutas import animales_por_caravana, partos_para_alertar
from app.nucleo.opciones import DIAS_ALERTA, ESTADOS_REPRODUCTIVOS, TIPOS_EVENTO
from app.nucleo.utilidades import describir_dias, dias_hasta, formatear_fecha, leer_fecha, normalizar_texto, separar_motivo

MAXIMO_CRIAS = 20


def _describir_crias(machos: int, hembras: int) -> str:
    total = machos + hembras
    nombre = {1: "", 2: "mellizos: ", 3: "trillizos: "}.get(total, f"{total} crías: ")
    partes = []
    if machos:
        partes.append(f"{machos} macho" + ("s" if machos > 1 else ""))
    if hembras:
        partes.append(f"{hembras} hembra" + ("s" if hembras > 1 else ""))
    return nombre + " y ".join(partes) if partes else "sin crías registradas"


def _singular(texto: str) -> str:
    """'vacas' -> 'vaca', 'ovinos' -> 'ovino', 'preñadas' -> 'prenada' (sin tildes)."""
    return normalizar_texto(texto).rstrip("s")


def _buscar_especie(palabra: str):
    """Devuelve la especie cuyo nombre coincide con la palabra (acepta plural), o None."""
    buscada = _singular(palabra)
    for especie in ganaderia_db.listar_especies():
        if _singular(especie["nombre"]) == buscada:
            return especie
    return None


def _separar_especie(argumento: str):
    """'ovino 12 preñada' -> (especie Ovino, '12 preñada'). Si no empieza con una especie, (None, argumento)."""
    palabras = argumento.split(maxsplit=1)
    if len(palabras) == 2:
        especie = _buscar_especie(palabras[0])
        if especie:
            return especie, palabras[1]
    return None, argumento


def _elegir_animal(caravana: str, especie=None):
    """Busca por caravana EXACTA (sin importar mayúsculas). Si no, sugiere parecidas.

    Si hay varios con la misma caravana, NO adivina: pide la especie.
    """
    especie_id = especie["id"] if especie else None
    encontrados = animales_por_caravana(caravana, especie_id)
    activos = [a for a in encontrados if a["estado"] == "activo"]
    if len(activos) == 1:
        return activos[0], None
    if len(activos) > 1:
        lineas = [f"Hay {len(activos)} animales con la caravana {caravana}:"]
        lineas += [f"  • {a['especie']} — {a['categoria'].lower()}" for a in activos]
        ejemplo = normalizar_texto(activos[0]["especie"])
        lineas.append(f"Escribí la especie antes de la caravana. Ejemplo: {ejemplo} {caravana}")
        return None, "\n".join(lineas)
    if encontrados:
        a = encontrados[0]
        return None, f"La caravana {a['caravana']} ({a['especie']}) está dada de baja ({a['estado']})."
    buscada = normalizar_texto(caravana)
    parecidas = [a["caravana"] for a in ganaderia_db.listar_animales()
                 if buscada in normalizar_texto(a["caravana"]) and (especie_id is None or a["especie_id"] == especie_id)]
    texto = f"❌ No encontré la caravana '{caravana}'" + (f" en {especie['nombre']}." if especie else ".")
    if parecidas:
        texto += "\n¿Es alguna de estas? " + ", ".join(parecidas[:10])
    return None, texto


def _linea_animal(a) -> str:
    texto = f"• {a['caravana']} — {a['categoria'].lower()} ({a['especie']})"
    if a["es_grupo"]:
        texto += f" · grupo de {a['cantidad']}"
    if a["rodeo"]:
        texto += f", {a['rodeo']}"
    if a["estado_reproductivo"] == "prenada":
        texto += " · preñada"
        if a["fecha_probable_parto"]:
            texto += f" (parto {formatear_fecha(a['fecha_probable_parto'])})"
    elif a["estado_reproductivo"] == "vacia":
        texto += " · vacía"
    return texto


def _resumen(animales) -> str:
    """Cuántos hay por especie y categoría. Los grupos suman su cantidad de cabezas."""
    por_especie = defaultdict(Counter)
    for a in animales:
        por_especie[a["especie"]][a["categoria"]] += a["cantidad"]
    total = sum(a["cantidad"] for a in animales)
    lineas = [f"🐄 {total} animales activos"]
    for especie, categorias in sorted(por_especie.items()):
        detalle = ", ".join(f"{nombre.lower()} {cantidad}" for nombre, cantidad in categorias.most_common())
        lineas.append(f"  • {especie}: {sum(categorias.values())} ({detalle})")
    reproductivas = [a for a in animales if a["reproductiva"]]
    if reproductivas:
        prenadas = sum(a["estado_reproductivo"] == "prenada" for a in reproductivas)
        vacias = sum(a["estado_reproductivo"] == "vacia" for a in reproductivas)
        lineas.append(f"\nHembras: {prenadas} preñadas · {vacias} vacías")
    partos = partos_para_alertar()
    if partos:
        lineas.append(f"🍼 Partos en los próximos {DIAS_ALERTA} días: {len(partos)} (ver /alertas)")
    lineas.append("\nFiltrá con: /animales <especie> | <categoría> | preñadas | vacías | <rodeo> | <caravana>")
    return "\n".join(lineas)


def comando_animales(argumento: str) -> str:
    """/animales  ->  resumen  |  /animales <filtro>  ->  lista (ovinos, vacas, preñadas, rodeo norte, 12...)"""
    animales = ganaderia_db.listar_animales()
    if not animales:
        return "No hay animales cargados. Cargalos desde la web: Animales → Listado."
    if not argumento:
        return _resumen(animales)

    filtro = normalizar_texto(argumento)
    singular = _singular(argumento)
    if singular in ("prenada", "vacia"):
        elegidos = [a for a in animales if a["estado_reproductivo"] == singular]
    elif any(_singular(a["especie"]) == singular for a in animales):
        elegidos = [a for a in animales if _singular(a["especie"]) == singular]
    elif any(_singular(a["categoria"]) == singular for a in animales):
        elegidos = [a for a in animales if _singular(a["categoria"]) == singular]
    else:
        elegidos = [
            a for a in animales
            if filtro in normalizar_texto(a["rodeo"]) or filtro in normalizar_texto(a["caravana"])
            or filtro in normalizar_texto(a["raza"])
        ]
    if not elegidos:
        return f"No encontré animales con '{argumento}'."
    lineas = [f"🐄 {len(elegidos)} animales · filtro: {argumento}"]
    lineas += [_linea_animal(a) for a in elegidos[:60]]
    if len(elegidos) > 60:
        lineas.append(f"… y {len(elegidos) - 60} más (mirá la lista completa en la web).")
    return "\n".join(lineas)


def comando_animal(argumento: str) -> str:
    """/animal [especie] <caravana>  ->  ficha y últimos eventos."""
    if not argumento:
        return "Formato: /animal <caravana>\nEjemplo: /animal 1234\nSi la caravana se repite: /animal ovino 1234"
    especie, caravana = _separar_especie(argumento)
    encontrados = animales_por_caravana(caravana, especie["id"] if especie else None)
    if especie and not encontrados and animales_por_caravana(argumento):
        # Era el nombre de un grupo que empieza como una especie (ej: "gallinas ponedoras").
        especie, caravana = None, argumento
        encontrados = animales_por_caravana(caravana)
    if len(encontrados) == 1:
        animal = encontrados[0]  # Se muestra aunque esté dado de baja.
    else:
        animal, error = _elegir_animal(caravana, especie)
        if error:
            return error
    nombre = "Grupo" if animal["es_grupo"] else "Caravana"
    lineas = [f"🐄 {nombre} {animal['caravana']}",
              f"Especie: {animal['especie']} · {animal['categoria']}"]
    if animal["es_grupo"]:
        lineas.append(f"Cantidad: {animal['cantidad']}")
    if animal["raza"]:
        lineas.append(f"Raza: {animal['raza']}")
    if animal["rodeo"]:
        lineas.append(f"Rodeo: {animal['rodeo']}")
    if animal["fecha_nacimiento"]:
        lineas.append(f"Nacimiento: {formatear_fecha(animal['fecha_nacimiento'])}")
    if animal["madre_caravana"]:
        lineas.append(f"Madre: {animal['madre_caravana']}")
    if animal["reproductiva"]:
        lineas.append(f"Estado: {ESTADOS_REPRODUCTIVOS[animal['estado_reproductivo']]}")
        if animal["fecha_probable_parto"]:
            dias = dias_hasta(animal["fecha_probable_parto"])
            lineas.append(f"Parto probable: {formatear_fecha(animal['fecha_probable_parto'])} ({describir_dias(dias)})")
    if animal["estado"] != "activo":
        lineas.append(f"⚠️ Dado de baja: {animal['estado']}")
    eventos = ganaderia_db.listar_eventos(animal["id"])[:5]
    if eventos:
        lineas.append("\nÚltimos eventos:")
        for e in eventos:
            texto = f"  • {formatear_fecha(e['fecha'])} {TIPOS_EVENTO.get(e['tipo'], e['tipo'])}"
            if e["tipo"] == "parto":
                texto += f" ({_describir_crias(e['crias_machos'], e['crias_hembras'])})"
            if e["resultado"]:
                texto += f": {ESTADOS_REPRODUCTIVOS.get(e['resultado'], e['resultado']).lower()}"
            if e["detalle"]:
                texto += f" — {e['detalle']}"
            lineas.append(texto)
    return "\n".join(lineas)


def _registrar(animal, tipo, **datos):
    """Registra el evento y traduce los errores a un mensaje para Telegram."""
    try:
        return ganaderia_db.registrar_evento(animal["id"], date.today(), tipo, **datos), None
    except ganaderia_db.EventoInvalido as error:
        return None, f"⚠️ {error}"


def comando_parto(argumento: str) -> str:
    """/parto [especie] <caravana> <crías> [- detalle]   crías: m (macho), h (hembra), mh, hh, mmh..."""
    uso = (
        "Formato: /parto <caravana> <crías> - <detalle opcional>\n"
        "Crías: m = macho, h = hembra. Mellizos: mh, mm o hh\n"
        "Ejemplo: /parto 1234 h\nEjemplo: /parto 1234 mh - parto difícil\n"
        "Si la caravana se repite: /parto porcino 12 mmmhhh"
    )
    principal, detalle = separar_motivo(argumento)
    especie, principal = _separar_especie(principal)
    palabras = principal.split()
    if len(palabras) != 2 or not set(palabras[1].lower()) <= {"m", "h"}:
        return uso
    crias = palabras[1].lower()
    if len(crias) > MAXIMO_CRIAS:
        return f"Máximo {MAXIMO_CRIAS} crías por parto.\n" + uso
    animal, error = _elegir_animal(palabras[0], especie)
    if error:
        return error
    machos, hembras = crias.count("m"), crias.count("h")
    actualizado, error = _registrar(animal, "parto", crias_machos=machos, crias_hembras=hembras, detalle=detalle)
    if error:
        return error
    texto = f"🍼 Parto registrado: {animal['caravana']} ({_describir_crias(machos, hembras)})."
    if animal["categoria"] != actualizado["categoria"]:
        texto += f"\nPasó de {animal['categoria'].lower()} a {actualizado['categoria'].lower()}."
    return texto + "\nPara cargar las crías con caravana, usá la web (Animales)."


def comando_aborto(argumento: str) -> str:
    """/aborto [especie] <caravana> [- detalle]"""
    principal, detalle = separar_motivo(argumento)
    especie, caravana = _separar_especie(principal)
    if not caravana:
        return "Formato: /aborto <caravana> - <detalle opcional>\nEjemplo: /aborto 1234"
    animal, error = _elegir_animal(caravana, especie)
    if error:
        return error
    _, error = _registrar(animal, "aborto", detalle=detalle)
    return error or f"Registrado aborto de {animal['caravana']}. Queda como vacía."


def comando_tacto(argumento: str) -> str:
    """/tacto [especie] <caravana> preñada|vacía [fecha probable de parto]"""
    uso = (
        "Formato: /tacto <caravana> <preñada|vacía> <fecha probable de parto opcional>\n"
        "Ejemplo: /tacto 1234 preñada 15/03/2027\nEjemplo: /tacto 1234 vacía"
    )
    especie, resto = _separar_especie(argumento)
    palabras = resto.split()
    if len(palabras) not in (2, 3):
        return uso
    resultado = normalizar_texto(palabras[1])
    if resultado not in ("prenada", "vacia"):
        return f"El resultado tiene que ser 'preñada' o 'vacía'.\n{uso}"
    fpp = None
    if len(palabras) == 3:
        fpp = leer_fecha(palabras[2])
        if fpp is None:
            return f"'{palabras[2]}' no es una fecha válida (usá dd/mm/aaaa).\n{uso}"
    animal, error = _elegir_animal(palabras[0], especie)
    if error:
        return error
    actualizado, error = _registrar(animal, "tacto", resultado=resultado, fecha_probable_parto=fpp)
    if error:
        return error
    if resultado == "vacia":
        return f"Tacto registrado: {animal['caravana']} vacía."
    texto = f"✅ Tacto registrado: {animal['caravana']} preñada."
    if actualizado["fecha_probable_parto"]:
        texto += f"\nParto probable: {formatear_fecha(actualizado['fecha_probable_parto'])}"
    else:
        texto += "\n(Sin fecha probable de parto: agregala al final del comando o desde la web)"
    return texto


def comando_servicio(argumento: str) -> str:
    """/servicio [especie] <caravana> [- toro o inseminación]"""
    principal, detalle = separar_motivo(argumento)
    especie, caravana = _separar_especie(principal)
    if not caravana:
        return "Formato: /servicio <caravana> - <toro o IA opcional>\nEjemplo: /servicio 1234 - toro 55"
    animal, error = _elegir_animal(caravana, especie)
    if error:
        return error
    actualizado, error = _registrar(animal, "servicio", detalle=detalle)
    if error:
        return error
    return (f"Servicio registrado: {animal['caravana']}. Si después el tacto da preñada sin fecha, "
            f"calculo el parto a {actualizado['dias_gestacion']} días del servicio.")


def lineas_partos(partos) -> list:
    lineas = []
    for a in partos:
        dias = dias_hasta(a["fecha_probable_parto"])
        icono = "🔴" if dias < 0 else "🟡"
        rodeo = f" ({a['rodeo']})" if a["rodeo"] else ""
        especie = "" if normalizar_texto(a["especie"]) == "vacuno" else f" [{a['especie']}]"
        lineas.append(f"{icono} {a['caravana']}{especie}{rodeo}: parto {describir_dias(dias)} ({formatear_fecha(a['fecha_probable_parto'])})")
    return lineas
