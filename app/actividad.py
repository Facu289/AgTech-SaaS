"""Última actividad: lo último que se cargó en la app, mezclado y del más nuevo al más viejo.

Lo usa la pantalla de Inicio. Junta órdenes de trabajo, movimientos de stock, trabajos y
services de máquinas, eventos de animales y cultivos cargados en los lotes.
(Cuando exista el módulo de Actividades por lote, se suma acá).

Cada cosa se ordena por CUÁNDO SE CARGÓ (creado_en), no por la fecha que dice: así "lo último
que pasó" es lo último que alguien anotó.
"""
from typing import Optional

from fastapi import APIRouter, Query

from app.nucleo import opciones
from app.nucleo.database import conectar
from app.nucleo.utilidades import formatear_cantidad

router = APIRouter(tags=["Inicio"])


def _orden(numero, orden_id):
    return f"OT {numero}" if numero else f"Orden #{orden_id}"


def ultima_actividad(limite=8):
    """Lista de {momento, tipo, titulo, detalle, enlace}, la más nueva primero."""
    items = []
    with conectar() as conexion:
        # Órdenes de trabajo: cuando se emitieron y cuando se realizaron.
        for o in conexion.execute(
            "SELECT id, numero, campo, tarea, estado, creado_en, actualizado_en FROM ordenes_trabajo "
            "ORDER BY id DESC LIMIT ?", (limite,)
        ):
            tarea = opciones.TAREAS_ORDEN.get(o["tarea"], o["tarea"])
            detalle = f"{tarea}{f' · {o['campo']}' if o['campo'] else ''}"
            enlace = f"orden.html?id={o['id']}"
            items.append({"momento": o["creado_en"], "tipo": "orden", "titulo": f"{_orden(o['numero'], o['id'])} cargada",
                          "detalle": detalle, "enlace": enlace})
            if o["estado"] == "realizada":
                items.append({"momento": o["actualizado_en"], "tipo": "orden",
                              "titulo": f"{_orden(o['numero'], o['id'])} realizada", "detalle": detalle, "enlace": enlace})

        # Movimientos de stock hechos a mano (los de las órdenes ya aparecen como "orden realizada").
        for m in conexion.execute(
            "SELECT mv.tipo, mv.cantidad, mv.motivo, mv.fecha, i.nombre, i.unidad, i.categoria FROM movimientos mv "
            "JOIN insumos i ON i.id = mv.insumo_id WHERE mv.orden_id IS NULL ORDER BY mv.id DESC LIMIT ?", (limite,)
        ):
            signo = "+" if m["tipo"] == "entrada" else "−"
            items.append({
                "momento": m["fecha"], "tipo": "stock",
                "titulo": f"{'Entrada' if m['tipo'] == 'entrada' else 'Salida'} de {m['nombre']}",
                "detalle": f"{signo}{formatear_cantidad(m['cantidad'])} {m['unidad']}{f' · {m['motivo']}' if m['motivo'] else ''}",
                "enlace": f"{opciones.hoja_de(m['categoria'])}.html",
            })

        # Máquinas: trabajos (ha) y services/arreglos.
        for t in conexion.execute(
            "SELECT t.maquina_id, t.tipo, t.hectareas, t.lote, t.creado_en, m.nombre FROM trabajos t "
            "JOIN maquinas m ON m.id = t.maquina_id ORDER BY t.id DESC LIMIT ?", (limite,)
        ):
            items.append({
                "momento": t["creado_en"], "tipo": "maquina",
                "titulo": f"{opciones.TIPOS_TRABAJO.get(t['tipo'], t['tipo'])} · {t['nombre']}",
                "detalle": f"{formatear_cantidad(t['hectareas'])} ha{f' · lote {t['lote']}' if t['lote'] else ''}",
                "enlace": f"maquina.html?id={t['maquina_id']}",
            })
        for s in conexion.execute(
            "SELECT s.maquina_id, s.tipo, s.descripcion, s.creado_en, m.nombre FROM mantenimientos s "
            "JOIN maquinas m ON m.id = s.maquina_id ORDER BY s.id DESC LIMIT ?", (limite,)
        ):
            items.append({
                "momento": s["creado_en"], "tipo": "maquina",
                "titulo": f"{opciones.TIPOS_MANTENIMIENTO.get(s['tipo'], s['tipo'])} · {s['nombre']}",
                "detalle": s["descripcion"], "enlace": f"maquina.html?id={s['maquina_id']}",
            })

        # Ganadería: eventos (parto, tacto, sanidad...).
        for e in conexion.execute(
            "SELECT e.animal_id, e.tipo, e.detalle, e.creado_en, a.caravana FROM eventos_animales e "
            "JOIN animales a ON a.id = e.animal_id ORDER BY e.id DESC LIMIT ?", (limite,)
        ):
            items.append({
                "momento": e["creado_en"], "tipo": "animal",
                "titulo": f"{opciones.TIPOS_EVENTO.get(e['tipo'], e['tipo'])} · caravana {e['caravana']}",
                "detalle": e["detalle"], "enlace": f"animal.html?id={e['animal_id']}",
            })

        # Lotes: cultivos cargados.
        for c in conexion.execute(
            "SELECT lc.lote_id, lc.ciclo, lc.creado_en, l.nombre, l.campo, cu.nombre AS cultivo, ca.nombre AS campania "
            "FROM lote_cultivos lc JOIN lotes l ON l.id = lc.lote_id JOIN cultivos cu ON cu.id = lc.cultivo_id "
            "JOIN campanias ca ON ca.id = lc.campania_id ORDER BY lc.id DESC LIMIT ?", (limite,)
        ):
            lote = f"{c['campo']} {c['nombre']}".strip()
            items.append({
                "momento": c["creado_en"], "tipo": "lote",
                "titulo": f"{c['cultivo']}{' 2ª' if c['ciclo'] == 'segunda' else ''} en {lote}",
                "detalle": f"Campaña {c['campania']}", "enlace": f"lote.html?id={c['lote_id']}",
            })

    # Las fechas están en texto "AAAA-MM-DD HH:MM:SS": ordenarlas como texto da el orden correcto.
    items.sort(key=lambda item: item["momento"] or "", reverse=True)
    return items[:limite]


@router.get("/actividad")
def ver_actividad(limite: Optional[int] = Query(default=8, ge=1, le=50)):
    return ultima_actividad(limite)
