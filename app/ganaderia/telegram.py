"""Comandos de Telegram de animales: /animales, /animal, /parto, /aborto, /tacto, /servicio."""
from collections import Counter
from datetime import date

from app.ganaderia import db as ganaderia_db
from app.ganaderia.rutas import animal_por_caravana, partos_para_alertar
from app.nucleo.opciones import CATEGORIAS_ANIMAL, DIAS_ALERTA, ESTADOS_REPRODUCTIVOS, HEMBRAS, TIPOS_EVENTO
from app.nucleo.utilidades import describir_dias, dias_hasta, formatear_fecha, leer_fecha, normalizar_texto, separar_motivo


def _describir_crias(machos: int, hembras: int) -> str:
    total = machos + hembras
    nombre = {1: "", 2: "mellizos: ", 3: "trillizos: "}.get(total, f"{total} crías: ")
    partes = []
    if machos:
        partes.append(f"{machos} macho" + ("s" if machos > 1 else ""))
    if hembras:
        partes.append(f"{hembras} hembra" + ("s" if hembras > 1 else ""))
    return nombre + " y ".join(partes) if partes else "sin crías registradas"


def _elegir_animal(caravana: str):
    """Busca por caravana EXACTA (sin importar mayúsculas). Si no, sugiere parecidas."""
    animal = animal_por_caravana(caravana)
    if animal:
        if animal["estado"] != "activo":
            return None, f"La caravana {animal['caravana']} está dada de baja ({animal['estado']})."
        return animal, None
    buscada = normalizar_texto(caravana)
    parecidas = [a["caravana"] for a in ganaderia_db.listar_animales() if buscada in normalizar_texto(a["caravana"])]
    texto = f"❌ No encontré la caravana '{caravana}'."
    if parecidas:
        texto += "\n¿Es alguna de estas? " + ", ".join(parecidas[:10])
    return None, texto


def _linea_animal(a) -> str:
    texto = f"• {a['caravana']} — {CATEGORIAS_ANIMAL.get(a['categoria'], a['categoria']).lower()}"
    if a["rodeo"]:
        texto += f", {a['rodeo']}"
    if a["estado_reproductivo"] == "prenada":
        texto += " · preñada"
        if a["fecha_probable_parto"]:
            texto += f" (parto {formatear_fecha(a['fecha_probable_parto'])})"
    elif a["estado_reproductivo"] == "vacia":
        texto += " · vacía"
    return texto


def comando_animales(argumento: str) -> str:
    """/animales  ->  resumen  |  /animales <filtro>  ->  lista (vacas, preñadas, rodeo norte, 12...)"""
    animales = ganaderia_db.listar_animales()
    if not animales:
        return "No hay animales cargados. Cargalos desde la web: Animales → Listado."

    if not argumento:
        por_categoria = Counter(a["categoria"] for a in animales)
        lineas = [f"🐄 Rodeo: {len(animales)} animales activos"]
        for categoria, nombre in CATEGORIAS_ANIMAL.items():
            if por_categoria[categoria]:
                lineas.append(f"  • {nombre}s: {por_categoria[categoria]}")
        hembras_adultas = [a for a in animales if a["categoria"] in ("vaca", "vaquillona")]
        prenadas = sum(a["estado_reproductivo"] == "prenada" for a in hembras_adultas)
        vacias = sum(a["estado_reproductivo"] == "vacia" for a in hembras_adultas)
        lineas.append(f"\nVacas y vaquillonas: {prenadas} preñadas · {vacias} vacías")
        partos = partos_para_alertar()
        if partos:
            lineas.append(f"🍼 Partos en los próximos {DIAS_ALERTA} días: {len(partos)} (ver /alertas)")
        lineas.append("\nFiltrá con: /animales vacas | preñadas | vacías | <rodeo> | <caravana>")
        return "\n".join(lineas)

    filtro = normalizar_texto(argumento)
    singular = filtro.rstrip("s")  # "vacas" -> "vaca", "preñadas" -> "prenada"
    if singular in ("prenada", "vacia"):
        elegidos = [a for a in animales if a["estado_reproductivo"] == singular]
    elif singular in CATEGORIAS_ANIMAL:
        elegidos = [a for a in animales if a["categoria"] == singular]
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
    """/animal <caravana>  ->  ficha y últimos eventos."""
    if not argumento:
        return "Formato: /animal <caravana>\nEjemplo: /animal 1234"
    animal = animal_por_caravana(argumento)
    if animal is None:
        return _elegir_animal(argumento)[1]
    lineas = [f"🐄 Caravana {animal['caravana']}",
              f"Categoría: {CATEGORIAS_ANIMAL.get(animal['categoria'], animal['categoria'])}"]
    if animal["raza"]:
        lineas.append(f"Raza: {animal['raza']}")
    if animal["rodeo"]:
        lineas.append(f"Rodeo: {animal['rodeo']}")
    if animal["fecha_nacimiento"]:
        lineas.append(f"Nacimiento: {formatear_fecha(animal['fecha_nacimiento'])}")
    if animal["madre_caravana"]:
        lineas.append(f"Madre: {animal['madre_caravana']}")
    if animal["categoria"] in HEMBRAS:
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
    """/parto <caravana> <crías> [- detalle]   crías: m (macho), h (hembra), mh, hh, mmh..."""
    uso = (
        "Formato: /parto <caravana> <crías> - <detalle opcional>\n"
        "Crías: m = macho, h = hembra. Mellizos: mh, mm o hh\n"
        "Ejemplo: /parto 1234 h\nEjemplo: /parto 1234 mh - parto difícil"
    )
    principal, detalle = separar_motivo(argumento)
    palabras = principal.split()
    if len(palabras) != 2 or not set(palabras[1].lower()) <= {"m", "h"}:
        return uso
    crias = palabras[1].lower()
    if len(crias) > 5:
        return "Máximo 5 crías por parto.\n" + uso
    animal, error = _elegir_animal(palabras[0])
    if error:
        return error
    machos, hembras = crias.count("m"), crias.count("h")
    actualizado, error = _registrar(animal, "parto", crias_machos=machos, crias_hembras=hembras, detalle=detalle)
    if error:
        return error
    texto = f"🍼 Parto registrado: {animal['caravana']} ({_describir_crias(machos, hembras)})."
    if animal["categoria"] != actualizado["categoria"]:
        texto += f"\nPasó de {animal['categoria']} a {actualizado['categoria']}."
    return texto + "\nPara cargar las crías con caravana, usá la web (Animales)."


def comando_aborto(argumento: str) -> str:
    """/aborto <caravana> [- detalle]"""
    caravana, detalle = separar_motivo(argumento)
    if not caravana:
        return "Formato: /aborto <caravana> - <detalle opcional>\nEjemplo: /aborto 1234"
    animal, error = _elegir_animal(caravana)
    if error:
        return error
    _, error = _registrar(animal, "aborto", detalle=detalle)
    return error or f"Registrado aborto de {animal['caravana']}. Queda como vacía."


def comando_tacto(argumento: str) -> str:
    """/tacto <caravana> preñada|vacía [fecha probable de parto]"""
    uso = (
        "Formato: /tacto <caravana> <preñada|vacía> <fecha probable de parto opcional>\n"
        "Ejemplo: /tacto 1234 preñada 15/03/2027\nEjemplo: /tacto 1234 vacía"
    )
    palabras = argumento.split()
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
    animal, error = _elegir_animal(palabras[0])
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
    """/servicio <caravana> [- toro o inseminación]"""
    caravana, detalle = separar_motivo(argumento)
    if not caravana:
        return "Formato: /servicio <caravana> - <toro o IA opcional>\nEjemplo: /servicio 1234 - toro 55"
    animal, error = _elegir_animal(caravana)
    if error:
        return error
    _, error = _registrar(animal, "servicio", detalle=detalle)
    if error:
        return error
    return (f"Servicio registrado: {animal['caravana']}. Si después el tacto da preñada sin fecha, "
            "calculo el parto a 283 días del servicio.")


def lineas_partos(partos) -> list:
    lineas = []
    for a in partos:
        dias = dias_hasta(a["fecha_probable_parto"])
        icono = "🔴" if dias < 0 else "🟡"
        rodeo = f" ({a['rodeo']})" if a["rodeo"] else ""
        lineas.append(f"{icono} {a['caravana']}{rodeo}: parto {describir_dias(dias)} ({formatear_fecha(a['fecha_probable_parto'])})")
    return lineas
