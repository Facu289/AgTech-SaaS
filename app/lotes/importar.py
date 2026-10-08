"""Pasar lotes de otra app a AgroApp (y de AgroApp a otra): KMZ, KML y GeoJSON.

- KML: el formato de Google Earth (texto XML). Cada lote es un "Placemark" con nombre y polígono.
- KMZ: un KML comprimido en .zip (lo que exportan Google Earth y muchas apps de campo).
- GeoJSON: el mismo formato en que AgroApp guarda los polígonos.

Este archivo NO toca la base: solo convierte archivos en una lista de {nombre, geometria}
y lotes en un KML. Quién guarda es app/lotes/rutas.py.
"""
import io
import json
import xml.etree.ElementTree as ET
import zipfile

from app.lotes import geometria

MAXIMO_DESCOMPRIMIDO = 50 * 1024 * 1024  # 50 MB: frena archivos "bomba" que se inflan al descomprimir.


class ArchivoInvalido(ValueError):
    """El archivo no se pudo leer (formato desconocido, roto o sin polígonos)."""


# ---------- Leer ----------

def leer_archivo(nombre_archivo: str, contenido: bytes):
    """Devuelve (lotes, errores).

    lotes: [{"nombre", "geometria", "hectareas"}] ya validados (como los guarda la app).
    errores: textos para el usuario, uno por cada forma que no se pudo usar.
    """
    extension = nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""
    if extension == "kmz" or contenido[:2] == b"PK":  # "PK" = así empieza todo archivo .zip
        crudos = _leer_kml(_kml_dentro_del_kmz(contenido))
    elif extension in ("geojson", "json") or contenido.lstrip()[:1] in (b"{", b"["):
        crudos = _leer_geojson(contenido)
    elif extension == "kml" or b"<kml" in contenido[:2000]:
        crudos = _leer_kml(contenido)
    else:
        raise ArchivoInvalido("formato no reconocido: usá un archivo .kmz, .kml o .geojson")

    lotes, errores = [], []
    for numero, (nombre, poligono, campo) in enumerate(crudos, start=1):
        nombre = (nombre or "").strip()[:80] or f"Lote {numero}"
        campo = (campo or "").strip()[:80]
        try:
            limpio = geometria.validar_poligono(poligono)
        except ValueError as error:
            errores.append(f"«{nombre}»: {error}")
            continue
        lotes.append({"campo": campo, "nombre": nombre, "geometria": limpio, "hectareas": geometria.hectareas(limpio)})

    if not lotes and not errores:
        raise ArchivoInvalido("el archivo no tiene polígonos (¿son puntos o líneas?)")
    _nombres_sin_repetir(lotes)
    return lotes, errores


def _nombres_sin_repetir(lotes):
    """Si el archivo trae dos "Lote 4" en el mismo campo, el segundo pasa a "Lote 4 (2)" (o el primer número libre)."""
    usados = set()
    for lote in lotes:
        base, numero = lote["nombre"], 2
        while (lote["campo"].lower(), lote["nombre"].lower()) in usados:
            lote["nombre"] = f"{base} ({numero})"
            numero += 1
        usados.add((lote["campo"].lower(), lote["nombre"].lower()))


def _kml_dentro_del_kmz(contenido: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as kmz:
            kmls = [info for info in kmz.infolist() if info.filename.lower().endswith(".kml")]
            if not kmls:
                raise ArchivoInvalido("el KMZ no tiene ningún .kml adentro")
            # El principal suele llamarse doc.kml; si no, el primero.
            elegido = next((i for i in kmls if i.filename.lower().endswith("doc.kml")), kmls[0])
            if elegido.file_size > MAXIMO_DESCOMPRIMIDO:
                raise ArchivoInvalido("el KMZ es demasiado grande")
            return kmz.read(elegido)
    except zipfile.BadZipFile:
        raise ArchivoInvalido("el KMZ está dañado (no se pudo descomprimir)")


def _sin_namespace(etiqueta: str) -> str:
    """'{http://www.opengis.net/kml/2.2}Placemark' -> 'Placemark' (cada versión de KML usa otro)."""
    return etiqueta.rsplit("}", 1)[-1]


def _hijos(elemento, nombre):
    return [hijo for hijo in elemento.iter() if _sin_namespace(hijo.tag) == nombre]


def _coordenadas(texto: str):
    """'-63.9,-31.6,0 -63.8,-31.6,0 ...' -> [[-63.9, -31.6], [-63.8, -31.6], ...] (la altura se descarta)."""
    puntos = []
    for trozo in (texto or "").split():
        valores = trozo.split(",")
        if len(valores) < 2:
            continue
        try:
            puntos.append([float(valores[0]), float(valores[1])])
        except ValueError:
            raise ArchivoInvalido(f"coordenada inválida en el archivo: {trozo[:40]}")
    return puntos


def _carpeta_de(placemark, padres):
    """El nombre de la carpeta (Folder) donde está el lote: muchas apps agrupan los lotes por campo así."""
    elemento = padres.get(placemark)
    while elemento is not None:
        if _sin_namespace(elemento.tag) == "Folder":
            return next((h.text for h in elemento if _sin_namespace(h.tag) == "name" and h.text), "")
        elemento = padres.get(elemento)
    return ""


def _leer_kml(contenido: bytes):
    """Devuelve [(nombre, poligono_geojson, campo)]. Un Placemark con varios polígonos da varios lotes.

    El campo propuesto es el nombre de la carpeta (Folder) que lo contiene (en la vista previa se cambia).
    """
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as error:
        raise ArchivoInvalido(f"el KML está mal armado ({error})")

    padres = {hijo: padre for padre in raiz.iter() for hijo in padre}  # ElementTree no sabe "quién es mi padre".
    resultado = []
    for placemark in _hijos(raiz, "Placemark"):
        campo = _carpeta_de(placemark, padres)
        nombre = next((h.text for h in placemark if _sin_namespace(h.tag) == "name" and h.text), "")
        formas = []
        for poligono in _hijos(placemark, "Polygon"):
            anillos = []
            for borde in _hijos(poligono, "outerBoundaryIs") + _hijos(poligono, "innerBoundaryIs"):
                for coords in _hijos(borde, "coordinates"):
                    anillos.append(_coordenadas(coords.text))
            if anillos:
                formas.append({"type": "Polygon", "coordinates": anillos})
        # Algunas apps exportan el borde del lote como una LÍNEA cerrada en vez de un polígono.
        if not formas:
            for linea in _hijos(placemark, "LineString") + _hijos(placemark, "LinearRing"):
                puntos = [p for c in _hijos(linea, "coordinates") for p in _coordenadas(c.text)]
                if len(puntos) >= 4 and puntos[0] == puntos[-1]:
                    formas.append({"type": "Polygon", "coordinates": [puntos]})
        for numero, forma in enumerate(formas, start=1):
            resultado.append((f"{nombre} ({numero})" if len(formas) > 1 else nombre, forma, campo))
    return resultado


CLAVES_NOMBRE = ("nombre", "name", "lote", "field", "field_name", "potrero", "id")
CLAVES_CAMPO = ("campo", "establecimiento", "farm", "farm_name", "estancia")


def _de_propiedades(propiedades, claves):
    """Busca un dato entre las propiedades (cada app le pone otro nombre a la columna)."""
    if not isinstance(propiedades, dict):
        return ""
    por_clave = {str(k).lower(): v for k, v in propiedades.items()}
    for clave in claves:
        valor = por_clave.get(clave)
        if valor not in (None, ""):
            return str(valor)
    return ""


def _leer_geojson(contenido: bytes):
    try:
        datos = json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArchivoInvalido("el GeoJSON está mal armado")

    if isinstance(datos, dict) and datos.get("type") == "FeatureCollection":
        elementos = datos.get("features") or []
    elif isinstance(datos, list):
        elementos = datos
    else:
        elementos = [datos]

    resultado = []
    for elemento in elementos:
        if not isinstance(elemento, dict):
            continue
        if elemento.get("type") == "Feature":
            propiedades = elemento.get("properties")
            forma = elemento.get("geometry") or {}
            nombre, campo = _de_propiedades(propiedades, CLAVES_NOMBRE), _de_propiedades(propiedades, CLAVES_CAMPO)
        else:
            forma, nombre, campo = elemento, "", ""
        if forma.get("type") == "Polygon":
            resultado.append((nombre, forma, campo))
        elif forma.get("type") == "MultiPolygon":
            partes = forma.get("coordinates") or []
            for numero, anillos in enumerate(partes, start=1):
                parte = {"type": "Polygon", "coordinates": anillos}
                resultado.append((f"{nombre} ({numero})" if len(partes) > 1 and nombre else nombre, parte, campo))
    return resultado


# ---------- Escribir (exportar a KML) ----------

def _color_kml(color_web: str, opacidad: str) -> str:
    """'#16A34A' (web: rojo-verde-azul) -> 'aa4AA316' (KML: opacidad-azul-verde-rojo, al revés)."""
    rojo, verde, azul = color_web[1:3], color_web[3:5], color_web[5:7]
    return f"{opacidad}{azul}{verde}{rojo}".lower()


def armar_kml(lotes, titulo="Lotes AgroApp") -> bytes:
    """Un KML con los lotes (con forma). Si traen "cultivos", se pintan con el color del primero.

    Se arma con ElementTree (y no pegando textos): así un nombre con "<" o "&" no rompe el archivo.
    """
    ET.register_namespace("", "http://www.opengis.net/kml/2.2")
    ns = "{http://www.opengis.net/kml/2.2}"
    kml = ET.Element(f"{ns}kml")
    documento = ET.SubElement(kml, f"{ns}Document")
    ET.SubElement(documento, f"{ns}name").text = titulo

    carpetas = {}
    for lote in lotes:
        if not lote.get("geometria"):
            continue
        campo = lote.get("campo") or ""
        if campo and campo not in carpetas:
            carpetas[campo] = ET.SubElement(documento, f"{ns}Folder")
            ET.SubElement(carpetas[campo], f"{ns}name").text = campo
        cultivos = lote.get("cultivos") or []
        color = cultivos[0]["color"] if cultivos else "#FACC15"
        marca = ET.SubElement(carpetas.get(campo, documento), f"{ns}Placemark")
        ET.SubElement(marca, f"{ns}name").text = lote["nombre"]
        detalle = [f"{lote['hectareas']:.2f} ha".replace(".", ",")] if lote.get("hectareas") is not None else []
        detalle += [("2ª " if c["ciclo"] == "segunda" else "") + c["cultivo"] for c in cultivos]
        if lote.get("observaciones"):
            detalle.append(lote["observaciones"])
        ET.SubElement(marca, f"{ns}description").text = " · ".join(detalle)
        estilo = ET.SubElement(marca, f"{ns}Style")
        linea = ET.SubElement(estilo, f"{ns}LineStyle")
        ET.SubElement(linea, f"{ns}color").text = _color_kml(color, "ff")
        ET.SubElement(linea, f"{ns}width").text = "2"
        relleno = ET.SubElement(estilo, f"{ns}PolyStyle")
        ET.SubElement(relleno, f"{ns}color").text = _color_kml(color, "66")

        poligono = ET.SubElement(marca, f"{ns}Polygon")
        anillos = lote["geometria"]["coordinates"]
        for numero, anillo in enumerate(anillos):
            borde = ET.SubElement(poligono, f"{ns}{'outerBoundaryIs' if numero == 0 else 'innerBoundaryIs'}")
            anillo_kml = ET.SubElement(ET.SubElement(borde, f"{ns}LinearRing"), f"{ns}coordinates")
            anillo_kml.text = " ".join(f"{lon},{lat},0" for lon, lat in anillo)

    return ET.tostring(kml, encoding="utf-8", xml_declaration=True)
