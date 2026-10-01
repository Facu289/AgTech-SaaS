"""Todos los valores permitidos de la app, en UN SOLO lugar.

Cada diccionario es  {valor que se guarda en la base: nombre que ve el usuario}.
- El backend los usa para validar (Pydantic) y para Telegram.
- La web los pide a GET /opciones, así no hay que repetirlos en JavaScript.

Para agregar una opción nueva, sumala acá y listo.
Regla: los valores (la parte izquierda) van en minúsculas, sin tildes ni espacios.
"""

# ---------- Insumos ----------

CATEGORIAS = {
    "agroquimico": "Agroquímico",
    "fertilizante": "Fertilizante",
    "semilla": "Semilla",
    "combustible": "Combustible",
    "repuesto": "Repuesto",
    "balanceado": "Balanceado",
    "medicamento": "Medicamento",
    "otro": "Otro",
}

# Subcategorías por categoría. Las categorías que no aparecen acá no tienen.
# IMPORTANTE: ningún valor se repite entre categorías, porque en Telegram
# "/nuevo glifosato herbicida litros" deduce la categoría a partir de "herbicida".
SUBCATEGORIAS = {
    "agroquimico": {
        "herbicida": "Herbicida",
        "insecticida": "Insecticida",
        "fungicida": "Fungicida",
        "coadyuvante": "Coadyuvante",
        "curasemilla": "Curasemilla",
        "acaricida": "Acaricida",
        "fitorregulador": "Fitorregulador",
    },
    "fertilizante": {
        "nitrogenado": "Nitrogenado",
        "fosforado": "Fosforado",
        "potasico": "Potásico",
        "azufrado": "Azufrado",
        "compuesto": "Compuesto",
        "foliar": "Foliar",
    },
    "semilla": {
        "soja": "Soja",
        "maiz": "Maíz",
        "trigo": "Trigo",
        "girasol": "Girasol",
        "sorgo": "Sorgo",
        "cebada": "Cebada",
        "pastura": "Pastura",
    },
    "repuesto": {
        "general": "General",
        "filtros": "Filtros",
        "rodamientos": "Rodamientos",
        "correas": "Correas",
        "hidraulica": "Hidráulica",
        "electrica": "Eléctrica",
        "neumaticos": "Neumáticos",
        "lubricantes": "Lubricantes",
    },
    "medicamento": {
        "vacuna": "Vacuna",
        "antiparasitario": "Antiparasitario",
        "antibiotico": "Antibiótico",
        "vitaminico": "Vitamínico",
    },
}

UNIDADES = {
    "kg": "kg",
    "litros": "litros",
    "bolsas": "bolsas",
    "unidades": "unidades",
}

# ---------- Maquinaria ----------

TIPOS_MAQUINA = {
    "tractor": "Tractor",
    "cosechadora": "Cosechadora",
    "sembradora": "Sembradora",
    "pulverizadora": "Pulverizadora",
    "fertilizadora": "Fertilizadora",
    "drone": "Drone",
    "tolva": "Tolva",
    "camioneta": "Camioneta",
    "camion": "Camión",
    "implemento": "Implemento",
    "otro": "Otro",
}

TIPOS_MANTENIMIENTO = {
    "service": "Service",
    "arreglo": "Arreglo",
}

# Service programado: se mide con las horas de motor o (cosechadoras) con las de trilla.
MEDIDAS_SERVICE = {
    "motor": "Horas de motor",
    "trilla": "Horas de trilla",
}

# Se avisa cuando falta este porcentaje del intervalo (10% de 250 h = 25 h antes).
AVISO_SERVICE_PORCENTAJE = 10

TIPOS_TRABAJO = {
    "trilla": "Trilla",
    "siembra": "Siembra",
    "pulverizacion": "Pulverización",
    "fertilizacion": "Fertilización",
    "labranza": "Labranza",
    "otro": "Otro",
}

TIPOS_VENCIMIENTO = {
    "seguro": "Seguro",
    "licencia": "Licencia / carnet",
    "suscripcion": "Suscripción / app",
    "vtv": "VTV / RTO",
    "habilitacion": "Habilitación",
    "patente": "Patente",
    "otro": "Otro",
}

# En estos vencimientos se muestra el N° de serie del monitor de la máquina.
TIPOS_CON_MONITOR = ("licencia", "suscripcion")

RUBROS_CONTACTO = {
    "senal": "Señal / GPS",
    "repuestos": "Repuestos",
    "mecanico": "Mecánico",
    "veterinario": "Veterinario",
    "agronomo": "Agrónomo",
    "proveedor": "Proveedor",
    "contratista": "Contratista",
    "otro": "Otro",
}

# ---------- Ganadería ----------

# Las especies (vacuno, ovino, gallina...) y sus categorías las crea el usuario:
# están en la base (tablas especies y categorias_animal), no acá.
# Cada categoría dice su sexo: solo las hembras pueden estar preñadas.
SEXOS_ANIMAL = {
    "hembra": "Hembra",
    "macho": "Macho",
    "": "Sin especificar",
}

ESTADOS_REPRODUCTIVOS = {
    "": "Sin dato",
    "vacia": "Vacía",
    "prenada": "Preñada",
}

ESTADOS_ANIMAL = {
    "activo": "Activo",
    "vendido": "Vendido",
    "muerto": "Muerto",
}

TIPOS_EVENTO = {
    "parto": "Parto",
    "aborto": "Aborto",
    "tacto": "Tacto",
    "servicio": "Servicio",
    "sanidad": "Sanidad",
    "observacion": "Observación",
}

# Días de anticipación para las alertas (partos, vencimientos).
DIAS_ALERTA = 30


def subcategorias_de(categoria: str) -> dict:
    """Subcategorías válidas de una categoría ({} si no tiene)."""
    return SUBCATEGORIAS.get(categoria, {})


def categoria_de_subcategoria(subcategoria: str):
    """'herbicida' -> 'agroquimico'. Devuelve None si no es una subcategoría."""
    for categoria, subcategorias in SUBCATEGORIAS.items():
        if subcategoria in subcategorias:
            return categoria
    return None


def todas():
    """Todo junto, para GET /opciones (lo usa la web)."""
    return {
        "categorias": CATEGORIAS,
        "subcategorias": SUBCATEGORIAS,
        "unidades": UNIDADES,
        "tipos_maquina": TIPOS_MAQUINA,
        "tipos_mantenimiento": TIPOS_MANTENIMIENTO,
        "tipos_trabajo": TIPOS_TRABAJO,
        "medidas_service": MEDIDAS_SERVICE,
        "aviso_service_porcentaje": AVISO_SERVICE_PORCENTAJE,
        "tipos_vencimiento": TIPOS_VENCIMIENTO,
        "tipos_con_monitor": list(TIPOS_CON_MONITOR),
        "rubros_contacto": RUBROS_CONTACTO,
        "sexos_animal": SEXOS_ANIMAL,
        "estados_reproductivos": ESTADOS_REPRODUCTIVOS,
        "estados_animal": ESTADOS_ANIMAL,
        "tipos_evento": TIPOS_EVENTO,
        "dias_alerta": DIAS_ALERTA,
    }
