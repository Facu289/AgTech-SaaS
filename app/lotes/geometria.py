"""Cuentas con polígonos: revisar que el dibujo sea válido y calcular sus hectáreas.

El mapa manda el lote en formato GeoJSON (el estándar para guardar formas en un mapa):

    {"type": "Polygon", "coordinates": [[[lon, lat], [lon, lat], ..., [lon, lat]]]}

OJO: GeoJSON pone primero la LONGITUD (este-oeste) y después la LATITUD (norte-sur).
"coordinates" es una lista de anillos: el primero es el borde; los demás, huecos (si hubiera).
Un anillo está "cerrado": el último punto repite el primero.

El mismo cálculo de área está en web/js/lotes.js (para mostrar las hectáreas mientras dibujás).
Si cambiás uno, cambiá el otro.
"""
import math

# Elipsoide WGS84 (el de los GPS): radio en el ecuador y "achatamiento" de la Tierra.
RADIO_ECUADOR = 6378137.0
EXCENTRICIDAD_2 = 0.00669437999014

MAXIMO_PUNTOS = 5000  # Un lote dibujado a mano tiene decenas; esto frena datos absurdos.
DECIMALES = 7         # 7 decimales de grado ≈ 1 cm: más no aporta y agranda el texto guardado.


def _radio_local_2(latitud):
    """Radio de la Tierra (al cuadrado) en esa latitud.

    La Tierra no es una esfera perfecta: está un poco achatada en los polos. En vez de usar
    un radio único, usamos el que corresponde a la latitud del lote. Para un lote de campo
    (unos pocos km) el error queda muy por debajo del 0,1 %.
    """
    seno = math.sin(math.radians(latitud))
    w2 = 1 - EXCENTRICIDAD_2 * seno * seno
    radio_meridiano = RADIO_ECUADOR * (1 - EXCENTRICIDAD_2) / w2 ** 1.5  # norte-sur
    radio_normal = RADIO_ECUADOR / math.sqrt(w2)                         # este-oeste
    return radio_meridiano * radio_normal


def _area_anillo(anillo, radio_2):
    """Área (m²) de un anillo sobre la Tierra curva ("área geodésica").

    Es la fórmula que usan Leaflet y Turf: suma, punto por punto, la diferencia de
    longitud de los vecinos por el seno de la latitud. Da positivo o negativo según el
    sentido en que se dibujó: por eso se toma el valor absoluto.
    """
    cantidad = len(anillo) - 1  # El último punto repite el primero.
    if cantidad < 3:
        return 0.0
    total = 0.0
    for i in range(cantidad):
        anterior = anillo[i - 1] if i > 0 else anillo[cantidad - 1]
        siguiente = anillo[i + 1]
        total += (math.radians(siguiente[0]) - math.radians(anterior[0])) * math.sin(math.radians(anillo[i][1]))
    return abs(total * radio_2 / 2)


def hectareas(geometria):
    """Hectáreas de un polígono GeoJSON ya validado (borde menos huecos), con 2 decimales."""
    borde = geometria["coordinates"][0]
    latitud_media = sum(punto[1] for punto in borde[:-1]) / (len(borde) - 1)
    radio_2 = _radio_local_2(latitud_media)
    metros_2 = _area_anillo(borde, radio_2)
    for hueco in geometria["coordinates"][1:]:
        metros_2 -= _area_anillo(hueco, radio_2)
    return round(max(metros_2, 0) / 10000, 2)  # 1 ha = 10.000 m²


def validar_poligono(geometria):
    """Revisa que sea un polígono GeoJSON razonable y lo devuelve "limpio".

    Lanza ValueError con un mensaje para el usuario si algo no está bien.
    """
    if not isinstance(geometria, dict) or geometria.get("type") != "Polygon":
        raise ValueError("el dibujo tiene que ser un polígono")
    anillos = geometria.get("coordinates")
    if not isinstance(anillos, list) or not anillos:
        raise ValueError("el polígono no tiene puntos")

    limpios = []
    puntos_totales = 0
    for anillo in anillos:
        if not isinstance(anillo, list):
            raise ValueError("el polígono está mal armado")
        puntos = []
        for punto in anillo:
            if (
                not isinstance(punto, (list, tuple)) or len(punto) < 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in punto[:2])
            ):
                raise ValueError("hay un punto del polígono que no es una coordenada")
            longitud, latitud = float(punto[0]), float(punto[1])
            if not (-180 <= longitud <= 180 and -90 <= latitud <= 90):
                raise ValueError("hay un punto fuera del mapa (longitud o latitud imposible)")
            puntos.append([round(longitud, DECIMALES), round(latitud, DECIMALES)])
        if puntos and puntos[0] != puntos[-1]:
            puntos.append(list(puntos[0]))  # Lo cerramos nosotros si vino abierto.
        if len({tuple(p) for p in puntos}) < 3:
            raise ValueError("el polígono necesita al menos 3 puntos distintos")
        puntos_totales += len(puntos)
        limpios.append(puntos)

    if puntos_totales > MAXIMO_PUNTOS:
        raise ValueError(f"el polígono tiene demasiados puntos (máximo {MAXIMO_PUNTOS})")
    limpio = {"type": "Polygon", "coordinates": limpios}
    if hectareas(limpio) <= 0:
        raise ValueError("el polígono no tiene superficie (es demasiado chico o los puntos están en línea)")
    return limpio
