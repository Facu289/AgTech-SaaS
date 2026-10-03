"""Carga en lenguaje natural por Telegram, con Gemini (Google).

Idea clave: Gemini NO toca la base de datos. Solo TRADUCE lo que escribiste
a los comandos que ya existen:

    "gasté 20 litros de glifosato en el lote 4"  ->  /salida 20 glifosato - lote 4

Después, esos comandos pasan por las mismas validaciones de siempre.
Si el comando CAMBIA datos (entrada, parto, horas...), el bot primero muestra
lo que entendió y espera un "sí". Si solo CONSULTA (stock, alertas...), responde directo.

Configuración en el archivo .env:
    GEMINI_API_KEY=tu_clave        (se saca gratis en https://aistudio.google.com)
    GEMINI_MODEL=gemini-3.5-flash-lite   (opcional)
"""
import json
import os
import re
import time

import requests
from dotenv import load_dotenv

from app.ganaderia import db as ganaderia_db
from app.insumos import db as insumos_db
from app.maquinaria import db as maquinaria_db
from app.nucleo.utilidades import normalizar_texto

load_dotenv()

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"

# Comandos que la IA puede proponer. Los de escritura necesitan confirmación.
COMANDOS_ESCRITURA = {
    "/entrada", "/salida", "/nuevo", "/nota", "/hecha", "/horas", "/trabajo",
    "/service", "/arreglo", "/parto", "/tacto", "/servicio", "/aborto",
}
COMANDOS_LECTURA = {
    "/stock", "/quimicos", "/repuestos", "/notas", "/maquinas", "/vencimientos", "/services",
    "/animales", "/animal", "/crias", "/alertas", "/ayuda",
}
MAXIMO_COMANDOS = 5
MINUTOS_PARA_CONFIRMAR = 10

PALABRAS_SI = {"si", "s", "dale", "ok", "okey", "confirmo", "confirmar", "listo", "de una", "/si"}
PALABRAS_NO = {"no", "n", "cancelar", "cancela", "cancelo", "/no"}

# Lo que cada usuario tiene pendiente de confirmar: {usuario: (comandos, momento)}.
# Vive en memoria: si se reinicia el backend, se pierde (y hay que volver a pedirlo).
pendientes = {}


class ErrorGemini(Exception):
    """No se pudo usar Gemini (sin clave, sin internet, límite alcanzado...)."""


# ---------- Hablar con Gemini ----------

def _instrucciones(ayuda: str) -> str:
    """El texto que le explica a Gemini qué tiene que hacer."""
    insumos = [i["nombre"] for i in insumos_db.listar_insumos()]
    maquinas = [m["nombre"] for m in maquinaria_db.listar_maquinas()]
    caravanas = [f'{a["caravana"]} ({a["especie"]})' for a in ganaderia_db.listar_animales()][:500]
    especies = [e["nombre"] for e in ganaderia_db.listar_especies()]
    return f"""Sos el asistente de AgroApp, una app para un campo en Argentina.
Tu única tarea: traducir el mensaje del usuario a comandos de la app. No hacés nada más.

Comandos disponibles:
{ayuda}

Datos cargados (usá EXACTAMENTE estos nombres cuando el usuario se refiera a ellos):
- Insumos: {", ".join(insumos) or "(ninguno)"}
- Máquinas: {", ".join(maquinas) or "(ninguna)"}
- Especies: {", ".join(especies) or "(ninguna)"}
- Caravanas de animales (y su especie): {", ".join(caravanas) or "(ninguna)"}

Reglas:
1. Respondé SOLO con un objeto JSON, sin texto antes ni después, con esta forma:
   {{"comandos": ["/salida 20 glifosato - lote 4"], "pregunta": ""}}
2. Cada comando en una sola línea, empezando con "/". Máximo {MAXIMO_COMANDOS} comandos.
3. Números en formato argentino: 1.500 = mil quinientos, 2,5 = dos y medio.
4. Si falta un dato imprescindible (cantidad, qué insumo, qué máquina...) o no está claro,
   NO inventes: devolvé "comandos": [] y en "pregunta" una pregunta corta para el usuario.
5. No inventes insumos, máquinas ni caravanas. Solo usá /nuevo si el usuario dice
   claramente que es un insumo nuevo.
6. Crías en /parto: m = macho, h = hembra (mellizos macho y hembra = mh).
   Si una caravana aparece en más de una especie, poné la especie antes: /tacto ovino 12 preñada
7. Si el mensaje no tiene que ver con la app, devolvé "comandos": [] y en "pregunta"
   explicá brevemente qué podés hacer.
"""


def consultar_gemini(instrucciones: str, mensaje: str) -> str:
    """Manda el pedido a Gemini y devuelve el texto que contesta.

    Separado en su propia función para poder reemplazarlo en los tests
    (así los tests no dependen de internet ni de una clave).
    """
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        raise ErrorGemini(
            "Para entender mensajes sin comando necesito una clave de Gemini.\n"
            "Agregá GEMINI_API_KEY=tu_clave en el archivo .env y reiniciá el backend.\n"
            "Mientras tanto, usá los comandos (/ayuda)."
        )
    modelo = os.getenv("GEMINI_MODEL", MODELO_POR_DEFECTO).strip()
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": f"{instrucciones}\n\nMensaje del usuario:\n{mensaje}"}]}]}
    try:
        respuesta = requests.post(
            URL_GEMINI.format(modelo=modelo),
            headers={"x-goog-api-key": clave, "Content-Type": "application/json"},
            json=cuerpo,
            timeout=30,
        )
    except requests.RequestException:
        raise ErrorGemini("No pude conectarme con Gemini (¿hay internet?). Usá los comandos por ahora (/ayuda).")

    if respuesta.status_code == 429:
        raise ErrorGemini("Se alcanzó el límite de uso de Gemini. Probá en un rato o usá los comandos (/ayuda).")
    if respuesta.status_code == 404:
        raise ErrorGemini(f"Gemini no reconoce el modelo '{modelo}'. Revisá GEMINI_MODEL en el .env.")
    if respuesta.status_code in (400, 401, 403):
        print(f"Gemini respondió {respuesta.status_code}: {respuesta.text[:300]}")
        raise ErrorGemini("Gemini rechazó el pedido (¿la clave GEMINI_API_KEY es correcta?).")
    if not respuesta.ok:
        raise ErrorGemini(f"Gemini respondió con un error ({respuesta.status_code}). Probá de nuevo.")

    try:
        partes = respuesta.json()["candidates"][0]["content"]["parts"]
        return "".join(parte.get("text", "") for parte in partes)
    except (KeyError, IndexError, ValueError):
        raise ErrorGemini("No entendí la respuesta de Gemini. Probá de nuevo o usá los comandos.")


def leer_respuesta(texto: str) -> dict:
    """Saca el JSON de lo que contestó Gemini (a veces lo envuelve en ```json ... ```)."""
    encontrado = re.search(r"\{.*\}", texto, re.DOTALL)
    if not encontrado:
        raise ErrorGemini("Gemini no devolvió lo que esperaba. Probá decirlo de otra forma.")
    try:
        datos = json.loads(encontrado.group())
    except json.JSONDecodeError:
        raise ErrorGemini("Gemini no devolvió lo que esperaba. Probá decirlo de otra forma.")
    comandos = datos.get("comandos") or []
    pregunta = datos.get("pregunta") or ""
    if not isinstance(comandos, list) or not isinstance(pregunta, str):
        raise ErrorGemini("Gemini no devolvió lo que esperaba. Probá decirlo de otra forma.")
    return {"comandos": [c for c in comandos if isinstance(c, str)], "pregunta": pregunta.strip()}


def comando_valido(comando: str) -> bool:
    """Seguridad: solo aceptamos comandos conocidos, de una línea y cortos."""
    if "\n" in comando or len(comando) > 300 or not comando.startswith("/"):
        return False
    nombre = comando.split()[0].lower()
    return nombre in COMANDOS_ESCRITURA or nombre in COMANDOS_LECTURA


# ---------- El flujo con el usuario ----------

def interpretar(texto: str, usuario, ayuda: str, ejecutar) -> str:
    """Atiende un mensaje SIN comando. "ejecutar" es la función que corre un comando.

    Devuelve lo que el bot tiene que contestar.
    """
    palabra = normalizar_texto(texto).strip("!.¡ ")

    # 1) ¿Está contestando "sí" o "no" a algo pendiente?
    pendiente = pendientes.get(usuario)
    if pendiente and time.time() - pendiente[1] > MINUTOS_PARA_CONFIRMAR * 60:
        pendientes.pop(usuario, None)
        pendiente = None
    if palabra in PALABRAS_SI | PALABRAS_NO:
        if not pendiente:
            return "No tengo nada pendiente para confirmar."
        pendientes.pop(usuario, None)
        if palabra in PALABRAS_NO:
            return "❌ Cancelado. No se registró nada."
        return "\n\n".join(ejecutar(comando) for comando in pendiente[0])

    # 2) Mensaje nuevo: se lo pasamos a Gemini.
    try:
        resultado = leer_respuesta(consultar_gemini(_instrucciones(ayuda), texto))
    except ErrorGemini as error:
        return f"🤖 {error}"

    comandos = [c.strip() for c in resultado["comandos"] if comando_valido(c.strip())][:MAXIMO_COMANDOS]
    if not comandos:
        return "🤖 " + (resultado["pregunta"] or "No entendí qué querés hacer. Probá con otras palabras o mirá /ayuda.")

    # 3) Si solo consulta, respondemos directo. Si cambia datos, pedimos confirmación.
    if all(c.split()[0].lower() in COMANDOS_LECTURA for c in comandos):
        return "\n\n".join(ejecutar(c) for c in comandos)

    pendientes[usuario] = (comandos, time.time())
    lista = "\n".join(f"• {c}" for c in comandos)
    return (
        f"🤖 Entendí esto:\n{lista}\n\n"
        "¿Lo registro? Respondé sí o no.\n"
        "(La próxima vez podés escribir el comando directamente)"
    )
