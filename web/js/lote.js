// =========================================================
// lote.js — ficha de un lote (lote.html?id=3): su mapa, sus datos,
// qué se sembró en cada campaña y los trabajos de maquinaria hechos ahí.
// =========================================================

const loteId = Number(new URLSearchParams(location.search).get("id"));
const titulo = document.getElementById("titulo");
const subtitulo = document.getElementById("subtitulo");

let lote = null;
let campanias = [];
let cultivos = [];
let opciones = null;

const contenedorMapa = document.getElementById("mapa");
// Un mapa solo para mirar: sin la rueda del mouse (si no, al bajar por la página se hace zoom sin querer).
const mapa = hayMapa(contenedorMapa) ? crearMapaSatelital(contenedorMapa, { scrollWheelZoom: false }) : null;
const capaLote = mapa ? L.featureGroup().addTo(mapa) : null;
let yaEncuadrado = false;

function dato(nombre, valor) {
  return [el("dt", {}, nombre), el("dd", {}, valor === "" || valor === null || valor === undefined ? "—" : valor)];
}

function mostrarDatos() {
  titulo.textContent = (lote.campo ? `${lote.campo} · ` : "") + lote.nombre + (lote.archivado ? " (archivado)" : "");
  document.title = `${lote.nombre} · AgroApp`;
  const actual = lote.historial.find((h) => h.campania_id === lote.historial[0]?.campania_id && h.ciclo === "primera") || lote.historial[0];
  subtitulo.textContent = [
    lote.hectareas !== null ? `${formatearCantidad(lote.hectareas)} ha` : "Sin hectáreas",
    actual ? `${actual.campania}: ${lote.historial.filter((h) => h.campania_id === actual.campania_id).map(nombreCultivo).join(" → ")}` : "Sin cultivos cargados",
  ].join(" · ");
  document.getElementById("datos").replaceChildren(
    ...dato("Campo", lote.campo),
    ...dato("Hectáreas", lote.hectareas !== null ? `${formatearCantidad(lote.hectareas)} ha` : ""),
    ...dato("Según el dibujo", lote.hectareas_calculadas !== null ? `${formatearCantidad(lote.hectareas_calculadas)} ha` : "Sin dibujar"),
    ...dato("Campañas cargadas", new Set(lote.historial.map((h) => h.campania_id)).size),
    ...dato("Observaciones", lote.observaciones),
  );
  document.getElementById("boton-mapa").href = `lotes.html?lote=${lote.id}`;
  document.getElementById("acciones-ficha").hidden = Boolean(lote.archivado);
}

function mostrarMapa() {
  if (!mapa) return;
  // El color es el del cultivo de la campaña más nueva.
  const ultima = lote.historial[0]?.campania_id;
  dibujarLotes(capaLote, [{ ...lote, cultivos: lote.historial.filter((h) => h.campania_id === ultima) }]);
  if (!yaEncuadrado && capaLote.getLayers().length) {
    mapa.fitBounds(capaLote.getBounds(), { padding: [20, 20], maxZoom: 17 });
    yaEncuadrado = true;
  }
  if (!lote.geometria) contenedorMapa.dataset.vacio = "Este lote no está dibujado: tocá «Editar en el mapa».";
}

function mostrarCultivos() {
  const cuerpo = document.getElementById("tabla-cultivos");
  cuerpo.replaceChildren();
  if (lote.historial.length === 0) cuerpo.append(filaVacia(10, "Todavía no tiene cultivos. Tocá «Agregar cultivo»."));
  for (const fila of lote.historial) {
    const hectareas = hectareasSembradas(fila, lote);
    // Producción en toneladas: hectáreas × quintales por hectárea ÷ 10 (1 t = 10 qq).
    const produccion = fila.rinde !== null && hectareas ? (hectareas * fila.rinde) / 10 : null;
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, fila.campania),
        el("td", {}, muestraCultivo(fila.color, nombreCultivo(fila))),
        el("td", {}, fila.variedad || "—"),
        el("td", {}, formatearFecha(fila.fecha_siembra) || "—"),
        el("td", {}, formatearFecha(fila.fecha_cosecha) || "—"),
        el("td", { className: "numero" }, formatearCantidad(hectareas) + (fila.hectareas === null ? " (todo)" : "")),
        el("td", { className: "numero" }, fila.rinde !== null ? formatearCantidad(fila.rinde) : "—"),
        el("td", { className: "numero" }, produccion !== null ? formatearCantidad(produccion) : "—"),
        el("td", { className: "suave chico" }, fila.observaciones),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("lapiz", "Editar", { onclick: () => editar(fila) }),
            botonIcono("basura", "Eliminar", { className: "peligro", onclick: () => eliminar(fila) }),
          ),
        ),
      ),
    );
  }
}

async function mostrarAplicaciones() {
  const cuerpo = document.getElementById("tabla-aplicaciones");
  const aplicaciones = await api("GET", `/lotes/${loteId}/aplicaciones`);
  cuerpo.replaceChildren();
  if (aplicaciones.length === 0) cuerpo.append(filaVacia(7, "Todavía no hay órdenes de trabajo para este lote."));
  for (const a of aplicaciones) {
    const estado = a.estado === "realizada" ? pill("Realizada", "verde") : pill("Pendiente", "ambar");
    a.productos.forEach((p, i) => {
      // La fecha, la orden, la tarea y el estado van solo en la primera fila de cada orden.
      const primera = i === 0;
      cuerpo.append(
        el(
          "tr",
          {},
          el("td", {}, primera ? formatearFecha(a.fecha) : ""),
          el("td", { style: "white-space:nowrap" }, primera ? el("a", { href: `orden.html?id=${a.orden_id}` }, a.numero ? `OT ${a.numero}` : `Orden #${a.orden_id}`) : ""),
          el("td", {}, primera ? opciones.tareas_orden[a.tarea] || a.tarea : ""),
          el("td", {}, primera ? estado : ""),
          el("td", {}, p.insumo),
          el("td", { className: "numero" }, p.dosis_ha !== null ? `${p.dosis_ha.toLocaleString("es-AR", { maximumFractionDigits: 3 })} ${p.unidad}/ha` : "—"),
          el("td", { className: "numero fuerte" }, p.cantidad !== null ? `${formatearCantidad(p.cantidad)} ${p.unidad}` : "—"),
        ),
      );
    });
    if (a.productos.length === 0) {
      cuerpo.append(el("tr", {}, el("td", {}, formatearFecha(a.fecha)), el("td", {}, `OT ${a.numero}`), el("td", {}, opciones.tareas_orden[a.tarea] || a.tarea), el("td", {}, estado), el("td", { colSpan: 3, className: "suave" }, "Sin productos")));
    }
  }
}

async function mostrarTrabajos() {
  const cuerpo = document.getElementById("tabla-trabajos");
  const buscado = normalizar(lote.nombre);
  const trabajos = (await api("GET", "/trabajos")).filter((t) => normalizar(t.lote) === buscado);
  cuerpo.replaceChildren();
  if (trabajos.length === 0) cuerpo.append(filaVacia(6, "No hay trabajos de maquinaria con este lote."));
  for (const t of trabajos) {
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", {}, formatearFecha(t.fecha)),
        el("td", {}, el("a", { href: `maquina.html?id=${t.maquina_id}` }, t.maquina_nombre)),
        el("td", {}, pillDeOpcion(opciones.tipos_trabajo, t.tipo)),
        el("td", { className: "numero" }, formatearCantidad(t.hectareas)),
        el("td", {}, t.cultivo || "—"),
        el("td", { className: "suave chico" }, t.observaciones),
      ),
    );
  }
}

async function cargar() {
  if (!loteId) {
    titulo.textContent = "Falta el lote";
    return;
  }
  try {
    [lote, campanias, cultivos] = await Promise.all([api("GET", `/lotes/${loteId}`), api("GET", "/campanias"), api("GET", "/cultivos")]);
    mostrarDatos();
    mostrarMapa();
    mostrarCultivos();
    await mostrarAplicaciones();
    await mostrarTrabajos();
  } catch (error) {
    titulo.textContent = error.estado === 404 ? "No existe ese lote" : `⚠️ ${error.message}`;
  }
}

// El lote "como lo ve la ventana": con sus cultivos (para proponer primera o segunda).
function loteParaVentana() {
  return { ...lote, cultivos: lote.historial };
}

document.getElementById("boton-cultivo").addEventListener("click", async () => {
  const guardado = await abrirVentanaCultivoLote({ lote: loteParaVentana(), campanias, cultivos, campaniaId: campaniaRecordada(campanias)?.id });
  if (!guardado) return;
  avisar(`✅ ${nombreCultivo(guardado)} en la campaña ${guardado.campania}`);
  cargar();
});

async function editar(fila) {
  const guardado = await abrirVentanaCultivoLote({ lote: loteParaVentana(), fila, campanias, cultivos });
  if (!guardado) return;
  avisar(`✅ Guardado: ${nombreCultivo(guardado)} (${guardado.campania})`);
  cargar();
}

async function eliminar(fila) {
  if (!confirmar(`¿Borrar ${nombreCultivo(fila)} de la campaña ${fila.campania}?`)) return;
  try {
    await api("DELETE", `/lote-cultivos/${fila.id}`);
  } catch (error) {
    avisar(error.message, "error");
  }
  cargar();
}

async function iniciar() {
  opciones = await cargarOpciones();
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
