"""El "cerebro" del bot: recibe el texto y decide qué contestar.

- Si empieza con "/", busca el comando en COMANDOS y lo ejecuta.
- Si no, lo interpreta Gemini (lenguaje_natural.py) y lo traduce a comandos.
"""
from typing import Optional

from app.alertas import obtener_alertas
from app.ganaderia import telegram as ganaderia_tg
from app.insumos import telegram as insumos_tg
from app.maquinaria import telegram as maquinaria_tg
from app.nucleo.utilidades import formatear_cantidad
from app.telegram import lenguaje_natural, notas


def comando_alertas(argumento: str) -> str:
    alertas = obtener_alertas()
    lineas = ["🔔 Alertas"]
    if alertas["stock_bajo"]:
        lineas.append("\n📦 Stock bajo")
        for i in alertas["stock_bajo"]:
            lineas.append(
                f"  • {i['nombre']}: {formatear_cantidad(i['cantidad'])} {i['unidad']} "
                f"(mínimo {formatear_cantidad(i['stock_minimo'])})"
            )
    if alertas["vencimientos"]:
        lineas.append("\n📅 Vencimientos")
        lineas += ["  " + maquinaria_tg._linea_vencimiento(v) for v in alertas["vencimientos"]]
    if alertas["services"]:
        lineas.append("\n🔧 Services")
        lineas += [f"  {p['maquina_nombre']}: " + maquinaria_tg._describir_plan(p) for p in alertas["services"]]
    if alertas["partos"]:
        lineas.append("\n🍼 Partos")
        lineas += ["  " + linea for linea in ganaderia_tg.lineas_partos(alertas["partos"])]
    if len(lineas) == 1:
        return "🔔 No hay alertas. Todo en orden. 👌"
    return "\n".join(lineas)


AYUDA = """Comandos de AgroApp

📦 Stock
/stock [filtro] - ver stock (ej: /stock herbicida)
/repuestos [filtro] - ver repuestos
/nuevo <nombre> <categoría o tipo> <unidad>
/entrada <cantidad> <insumo> - motivo
/salida <cantidad> <insumo> - motivo

🚜 Maquinaria
/maquinas [filtro] - horas y últimos services
/horas <máquina> <horas> - actualizar horómetro
/trabajo <máquina> <ha> <tipo> - lote
/service <máquina> - descripción
/arreglo <máquina> - descripción
/services [máquina] - service programado
/vencimientos - seguros, licencias, VTV...

🐄 Animales
/animales [filtro] - resumen o lista
/animal <caravana> - ficha
/parto <caravana> <crías: m/h> - detalle
/tacto <caravana> <preñada|vacía> [fecha parto]
/servicio <caravana> - toro o IA
/aborto <caravana> - detalle
/crias [especie] - resumen de partos y crías del año
Si una caravana se repite, poné la especie antes: /animal ovino 12

📝 Otros
/alertas - todo lo que requiere atención
💬 También podés escribir normal: "gasté 20 litros de glifosato en el lote 4"
/nota <texto> · /notas · /hecha <n>
/ayuda - esta ayuda"""

# Qué función responde cada comando. Todas reciben el texto después del comando.
COMANDOS = {
    "/start": lambda _: "¡Hola! Soy el bot de AgroApp 🌱. Escribí /ayuda para ver qué sé hacer.",
    "/ayuda": lambda _: AYUDA,
    "/stock": insumos_tg.comando_stock,
    "/repuestos": insumos_tg.comando_repuestos,
    "/nuevo": insumos_tg.comando_nuevo,
    "/entrada": lambda arg: insumos_tg.comando_movimiento("entrada", arg),
    "/salida": lambda arg: insumos_tg.comando_movimiento("salida", arg),
    "/nota": notas.comando_nota,
    "/notas": notas.comando_notas,
    "/hecha": notas.comando_hecha,
    "/maquinas": maquinaria_tg.comando_maquinas,
    "/horas": maquinaria_tg.comando_horas,
    "/trabajo": maquinaria_tg.comando_trabajo,
    "/service": lambda arg: maquinaria_tg.comando_mantenimiento("service", arg),
    "/arreglo": lambda arg: maquinaria_tg.comando_mantenimiento("arreglo", arg),
    "/vencimientos": maquinaria_tg.comando_vencimientos,
    "/services": maquinaria_tg.comando_services,
    "/animales": ganaderia_tg.comando_animales,
    "/animal": ganaderia_tg.comando_animal,
    "/parto": ganaderia_tg.comando_parto,
    "/aborto": ganaderia_tg.comando_aborto,
    "/crias": ganaderia_tg.comando_crias,
    "/crías": ganaderia_tg.comando_crias,
    "/tacto": ganaderia_tg.comando_tacto,
    "/servicio": ganaderia_tg.comando_servicio,
    "/alertas": comando_alertas,
}

# Telegram no acepta mensajes de más de 4096 caracteres.
LARGO_MAXIMO = 4000


def ejecutar_comando(texto: str) -> str:
    """Corre UN comando ("/stock herbicida") y devuelve la respuesta."""
    texto = texto.strip()

    # Separa "/nota comprar urea" en comando="/nota" y argumento="comprar urea".
    partes = texto.split(maxsplit=1)
    comando = partes[0].lower().split("@")[0] if partes else ""  # "/Stock@mi_bot" -> "/stock"
    argumento = partes[1].strip() if len(partes) > 1 else ""

    funcion = COMANDOS.get(comando)
    if funcion is None:
        return f"No entendí '{texto}'. Escribí /ayuda para ver los comandos."
    return funcion(argumento)


def generar_respuesta(texto: str, usuario: Optional[int] = None) -> str:
    """El 'cerebro' del bot: decide qué contestar a cada mensaje.

    - Si empieza con "/", es un comando.
    - Si no (o es /si, /no), es lenguaje natural: lo interpreta Gemini.
    """
    texto = texto.strip()
    primera = texto.split(maxsplit=1)[0].lower().split("@")[0] if texto else ""
    if texto.startswith("/") and primera not in ("/si", "/no"):
        respuesta = ejecutar_comando(texto)
    elif not texto:
        respuesta = "Escribí /ayuda para ver qué sé hacer."
    else:
        texto_natural = primera[1:] if primera in ("/si", "/no") else texto
        respuesta = lenguaje_natural.interpretar(texto_natural, usuario or 0, AYUDA, ejecutar_comando)

    if len(respuesta) > LARGO_MAXIMO:
        respuesta = respuesta[:LARGO_MAXIMO].rsplit("\n", 1)[0] + "\n\n… (cortado: usá un filtro o mirá la web)"
    return respuesta
