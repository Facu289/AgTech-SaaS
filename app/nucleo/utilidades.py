"""Funciones chicas que usan varias partes de la app: texto, números, fechas y búsqueda."""
import difflib
import math
import re
import unicodedata
from datetime import date, datetime, timedelta

# ---------- Texto ----------


def normalizar_texto(valor: str) -> str:
    """Pasa a minúsculas y saca tildes: ' Agroquímico ' -> 'agroquimico'."""
    sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower()


def separar_motivo(texto: str, por_defecto: str = ""):
    """'urea - compra' -> ('urea', 'compra'). Si no hay ' -', el motivo es por_defecto."""
    principal, _, motivo = texto.partition(" -")
    return principal.strip(), (motivo.strip() or por_defecto)


# ---------- Números ----------


def leer_cantidad(texto: str):
    """Convierte lo que escribe el usuario en un número MAYOR a 0. None si no es válido.

    Acepta: 20 | 2.5 | 2,5 | 1.500 (mil quinientos) | 1.500,5
    """
    numero = leer_numero(texto)
    if numero is None or numero <= 0:
        return None
    return numero


def leer_numero(texto: str):
    """Como leer_cantidad, pero acepta el 0 (sirve para horas, stock mínimo, etc.)."""
    texto = texto.strip()
    if "," in texto:
        # Formato argentino: el punto separa miles y la coma los decimales.
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        # "1.500" o "12.000": los puntos son separadores de miles.
        texto = texto.replace(".", "")
    try:
        cantidad = float(texto)
    except ValueError:
        return None
    if not math.isfinite(cantidad) or cantidad < 0:
        return None
    return cantidad


def formatear_cantidad(cantidad: float) -> str:
    """Número al estilo argentino: 1500.0 -> '1.500' | 2.5 -> '2,5' | 1234.567 -> '1.234,57'."""
    redondeado = round(cantidad, 2)
    if redondeado.is_integer():
        texto = f"{int(redondeado):,}"
    else:
        texto = f"{redondeado:,.2f}".rstrip("0")
    # Python usa "," para miles y "." para decimales: los intercambiamos.
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- Fechas ----------
# En la base las fechas se guardan como texto 'AAAA-MM-DD' (así se ordenan bien).


def leer_fecha(texto: str):
    """Convierte lo que escribe el usuario en una fecha. Devuelve None si no es válida.

    Acepta: hoy | ayer | 15/3 | 15/03/2026 | 15/03/26 | 2026-03-15
    """
    texto = normalizar_texto(texto)
    hoy = date.today()
    if texto == "hoy":
        return hoy
    if texto == "ayer":
        return hoy - timedelta(days=1)
    formatos = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y")
    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    try:  # "15/3" -> este año
        return datetime.strptime(f"{texto}/{hoy.year}", "%d/%m/%Y").date()
    except ValueError:
        return None


def formatear_fecha(valor) -> str:
    """'2026-03-15' (o un date) -> '15/03/2026'. Vacío si no hay fecha."""
    if not valor:
        return ""
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return valor.strftime("%d/%m/%Y")


def dias_hasta(valor) -> int:
    """Días que faltan desde hoy hasta la fecha (negativo si ya pasó)."""
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return (valor - date.today()).days


def describir_dias(dias: int) -> str:
    """3 -> 'en 3 días' | 0 -> 'hoy' | -2 -> 'hace 2 días'."""
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias > 0:
        return f"en {dias} días"
    if dias == -1:
        return "ayer"
    return f"hace {-dias} días"


# ---------- Búsqueda por nombre ----------


def buscar_por_nombre(elementos: list, texto: str, campo: str = "nombre") -> list:
    """Busca en una lista de diccionarios sin importar mayúsculas ni tildes.

    Si hay uno con el nombre exacto, devuelve solo ese.
    Si no, devuelve todos los que CONTIENEN el texto ("glifo" -> "Glifosato").
    """
    buscado = normalizar_texto(texto)
    exactos = [e for e in elementos if normalizar_texto(e[campo]) == buscado]
    if exactos:
        return exactos
    return [e for e in elementos if buscado in normalizar_texto(e[campo])]


def nombres_parecidos(elementos: list, texto: str, campo: str = "nombre") -> list:
    """Hasta 3 nombres parecidos (para detectar errores de tipeo)."""
    por_normalizado = {normalizar_texto(e[campo]): e[campo] for e in elementos}
    parecidos = difflib.get_close_matches(normalizar_texto(texto), por_normalizado, n=3, cutoff=0.6)
    return [por_normalizado[p] for p in parecidos]


def elegir_uno(elementos: list, texto: str, que: str, campo: str = "nombre"):
    """Busca un único elemento por nombre para los comandos de Telegram.

    Devuelve (elemento, None) si encontró uno solo,
    o (None, mensaje) explicando qué pasó (no existe / hay varios).
    """
    encontrados = buscar_por_nombre(elementos, texto, campo)
    if len(encontrados) == 1:
        return encontrados[0], None
    if len(encontrados) > 1:
        opciones = "\n".join(f"  • {e[campo]}" for e in encontrados[:15])
        return None, f"Hay varias coincidencias con '{texto}':\n{opciones}\nEscribí el nombre más completo."
    lineas = [f"❌ No encontré {que} '{texto}'."]
    parecidos = nombres_parecidos(elementos, texto, campo)
    if parecidos:
        lineas.append("¿Quisiste decir: " + ", ".join(parecidos) + "?")
    return None, "\n".join(lineas)
