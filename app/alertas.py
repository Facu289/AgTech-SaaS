"""Lo que requiere atención: stock bajo, vencimientos, services, partos y órdenes de trabajo pendientes.

Lo usan la API (GET /alertas, que muestra la web) y el comando /alertas de Telegram.
"""
from app.ganaderia.rutas import partos_para_alertar
from app.insumos.rutas import insumos_con_stock_bajo
from app.maquinaria import db as maquinaria_db
from app.maquinaria.rutas import vencimientos_para_alertar
from app.nucleo.utilidades import dias_hasta
from app.ordenes import db as ordenes_db


def ordenes_pendientes():
    """Órdenes emitidas que todavía no se aplicaron. "faltantes" = productos a los que no les alcanza el stock."""
    return [
        {"id": o["id"], "numero": o["numero"], "campo": o["campo"], "fecha_emision": o["fecha_emision"],
         "hectareas": o["hectareas"], "faltantes": [f["insumo"] for f in ordenes_db.faltantes(o)]}
        for o in ordenes_db.listar_ordenes(estado="pendiente")
    ]


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
        "ordenes_pendientes": ordenes_pendientes(),
    }
