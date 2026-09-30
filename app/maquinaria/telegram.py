"""Comandos de Telegram de maquinaria: /maquinas, /horas, /trabajo, /service, /arreglo, /services, /vencimientos."""
from datetime import date

from app.maquinaria import db as maquinaria_db
from app.maquinaria.rutas import vencimientos_para_alertar
from app.nucleo.opciones import DIAS_ALERTA, TIPOS_MANTENIMIENTO, TIPOS_MAQUINA, TIPOS_TRABAJO
from app.nucleo.utilidades import (
    describir_dias, dias_hasta, elegir_uno, formatear_cantidad, formatear_fecha, leer_cantidad,
    leer_numero, normalizar_texto, separar_motivo,
)


def _horas(valor) -> str:
    return f"{formatear_cantidad(valor)} h"


def _elegir_maquina(texto: str):
    return elegir_uno(maquinaria_db.listar_maquinas(), texto, "máquina")


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
    planes = maquinaria_db.listar_planes()
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
    maquinas = maquinaria_db.listar_maquinas()
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
        planes = [p for p in maquinaria_db.listar_planes(m["id"])]
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
    maquinaria_db.actualizar_horas(maquina["id"], horas_motor=horas)
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
    maquinaria_db.agregar_trabajo(maquina["id"], date.today(), tipo, hectareas, lote)
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

    planes = maquinaria_db.listar_planes(maquina["id"]) if tipo == "service" else []
    hechos = _planes_mencionados(planes, descripcion) if descripcion else []
    maquinaria_db.agregar_mantenimiento(
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
