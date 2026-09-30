"""Lo que requiere atención: stock bajo, vencimientos, services y partos.

Lo usan la API (GET /alertas, que muestra la web) y el comando /alertas de Telegram.
"""
from app.ganaderia.rutas import partos_para_alertar
from app.insumos.rutas import insumos_con_stock_bajo
from app.maquinaria import db as maquinaria_db
from app.maquinaria.rutas import vencimientos_para_alertar
from app.nucleo.utilidades import dias_hasta


def obtener_alertas() -> dict:
    return {
        "stock_bajo": insumos_con_stock_bajo(),
        "vencimientos": [
            {**v, "dias": dias_hasta(v["fecha_vencimiento"])} for v in vencimientos_para_alertar()
        ],
        "partos": [
            {**a, "dias": dias_hasta(a["fecha_probable_parto"])} for a in partos_para_alertar()
        ],
        "services": maquinaria_db.services_para_alertar(),
    }
