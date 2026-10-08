// =========================================================
// orden.js — una orden de trabajo: cargarla, editarla, realizarla e imprimirla.
//   orden.html        → orden nueva
//   orden.html?id=5   → la orden 5
//
// Cuentas (como en la planilla):
//   hectáreas de la orden = suma de las ha de sus lotes
//   dosis/ha = total ÷ hectáreas        (escribís una y se calcula la otra)
//   por tancada = total ÷ cantidad de tancadas
//   agua = caldo/ha × hectáreas − lo que suman los productos
// =========================================================

let ordenId = Number(new URLSearchParams(location.search).get("id")) || null;
const formOrden = document.getElementById("form-orden");
const camposOrden = document.getElementById("campos-orden");
const tablaLotes = document.getElementById("tabla-lotes");
const tablaProductos = document.getElementById("tabla-productos");
const pieProductos = document.getElementById("pie-productos");
const ventanaRealizar = document.getElementById("ventana-realizar");
const formRealizar = document.getElementById("form-realizar");

let opciones = null;
let orden = null; // la orden como está guardada (null = nueva)
let insumos = []; // productos del stock que se pueden usar
let filasLotes = []; // [{fila, lote, hectareas}]
let filasProductos = []; // [{fila, producto (select), dosis, total, porTancada, stock, base}]
let hayCambiosSinGuardar = false;

const COLOR_ESTADO = { pendiente: "ambar", realizada: "verde", anulada: "gris" };

// ---------- Cuentas ----------

function hectareasTotales() {
  return filasLotes.reduce((suma, f) => suma + (leerNumero(f.hectareas.value) || 0), 0);
}

function tancadas() {
  const valor = parseInt(formOrden.elements.tancadas.value, 10);
  return valor > 0 ? valor : null;
}

function insumoDe(id) {
  return insumos.find((i) => String(i.id) === String(id));
}

// Recalcula todo: totales o dosis de cada producto, por tancada, stock, agua y resumen.
function recalcular() {
  const hectareas = hectareasTotales();
  const nTancadas = tancadas();
  document.getElementById("total-ha").textContent = `${formatearCantidad(hectareas)} ha`;

  // Lo que pide cada producto del stock (si un producto se repite, se suma).
  const pedidoPorInsumo = {};
  for (const f of filasProductos) {
    if (f.base === "dosis") {
      const dosis = leerNumero(f.dosis.value);
      f.total.value = dosis !== null && hectareas > 0 ? numeroParaCampo(dosis * hectareas) : f.total.value;
    } else {
      const total = leerNumero(f.total.value);
      f.dosis.value = total !== null && hectareas > 0 ? numeroParaCampo(total / hectareas) : f.dosis.value;
    }
    const total = leerNumero(f.total.value) || 0;
    f.porTancada.textContent = nTancadas && total ? numeroParaCampo(total / nTancadas) : "—";
    if (f.producto.value) pedidoPorInsumo[f.producto.value] = (pedidoPorInsumo[f.producto.value] || 0) + total;
  }
  // Stock de cada fila: en rojo si no alcanza (solo importa mientras la orden está pendiente).
  for (const f of filasProductos) {
    const insumo = insumoDe(f.producto.value);
    f.stock.replaceChildren();
    if (!insumo) continue;
    const falta = (!orden || orden.estado === "pendiente") && pedidoPorInsumo[insumo.id] > insumo.cantidad + 1e-9;
    f.stock.append(el("span", { className: falta ? "texto-rojo fuerte" : "suave" }, `${formatearCantidad(insumo.cantidad)} ${insumo.unidad}`));
    if (falta) f.stock.title = "No alcanza el stock para esta orden";
  }

  // Agua y caldo.
  const caldoHa = leerNumero(formOrden.elements.caldo_ha.value);
  const productos = Object.values(pedidoPorInsumo).reduce((a, b) => a + b, 0);
  pieProductos.replaceChildren();
  if (caldoHa && hectareas > 0) {
    const caldo = caldoHa * hectareas;
    const agua = Math.max(caldo - productos, 0);
    pieProductos.append(
      el("tr", {}, el("td", {}, "Agua"), el("td", { className: "numero" }, numeroParaCampo(agua / hectareas)),
        el("td", { className: "numero" }, numeroParaCampo(agua)), el("td", { className: "numero" }, nTancadas ? numeroParaCampo(agua / nTancadas) : "—"),
        el("td", { className: "suave chico", colSpan: 2 }, "no se descuenta")),
      el("tr", { className: "fuerte" }, el("td", {}, "Total caldo"), el("td", { className: "numero" }, numeroParaCampo(caldoHa)),
        el("td", { className: "numero" }, numeroParaCampo(caldo)), el("td", { className: "numero" }, nTancadas ? numeroParaCampo(caldo / nTancadas) : "—"),
        el("td", { colSpan: 2 })),
    );
  }
  const partes = [`${formatearCantidad(hectareas)} ha`];
  if (nTancadas) partes.push(`${nTancadas} tancada${nTancadas === 1 ? "" : "s"} de ${formatearCantidad(hectareas / nTancadas)} ha`);
  if (caldoHa && hectareas) partes.push(`${formatearCantidad(caldoHa * hectareas)} l de caldo`);
  document.getElementById("resumen-caldo").textContent = partes.join(" · ");
}

// ---------- Filas de lotes y de productos ----------

function agregarLote(datos = {}) {
  const lote = el("input", { value: datos.lote ?? "", maxLength: 80, "aria-label": "Lote(s)", placeholder: "Ej: 31+32" });
  const hectareas = el("input", { value: numeroParaCampo(datos.hectareas, 2), "aria-label": "Hectáreas", placeholder: "ha" });
  hectareas.setAttribute("inputmode", "decimal");
  const fila = el("tr", {}, el("td", {}, lote), el("td", { className: "numero" }, hectareas));
  const registro = { fila, lote, hectareas };
  fila.append(el("td", {}, botonIcono("cerrar", "Quitar lote", {
    className: "peligro",
    onclick: () => {
      filasLotes = filasLotes.filter((f) => f !== registro);
      fila.remove();
      marcarCambios();
    },
  })));
  hectareas.addEventListener("input", recalcular);
  tablaLotes.append(fila);
  filasLotes.push(registro);
  return registro;
}

function opcionesProductos(select, elegido) {
  // Químicos primero, después el resto de los insumos (los repuestos no se aplican).
  const grupos = [["Químicos", insumos.filter((i) => i.hoja === "quimicos")], ["Insumos", insumos.filter((i) => i.hoja === "insumos")]];
  select.replaceChildren(el("option", { value: "" }, "Elegí un producto…"));
  for (const [titulo, lista] of grupos) {
    if (!lista.length) continue;
    const grupo = el("optgroup", { label: titulo });
    for (const i of lista) grupo.append(el("option", { value: i.id }, `${i.nombre} (${i.unidad})${i.archivado ? " — archivado" : ""}`));
    select.append(grupo);
  }
  select.value = elegido ?? "";
}

function agregarProducto(datos = {}) {
  const producto = el("select", { "aria-label": "Producto" });
  opcionesProductos(producto, datos.insumo_id);
  const dosis = el("input", { "aria-label": "Dosis por hectárea", placeholder: "dosis/ha" });
  const total = el("input", { value: numeroParaCampo(datos.cantidad_total), "aria-label": "Total", placeholder: "total" });
  dosis.setAttribute("inputmode", "decimal");
  total.setAttribute("inputmode", "decimal");
  const porTancada = el("td", { className: "numero" }, "—");
  const stock = el("td", { className: "numero" });
  const fila = el("tr", {}, el("td", {}, producto), el("td", { className: "numero" }, dosis), el("td", { className: "numero" }, total), porTancada, stock);
  // "base": el número que escribiste vos (el otro se calcula). Al abrir una orden guardada, la base es el total.
  const registro = { fila, producto, dosis, total, porTancada, stock, base: "total" };
  fila.append(el("td", {}, botonIcono("cerrar", "Quitar producto", {
    className: "peligro",
    onclick: () => {
      filasProductos = filasProductos.filter((f) => f !== registro);
      fila.remove();
      recalcular();
      marcarCambios();
    },
  })));
  dosis.addEventListener("input", () => {
    registro.base = "dosis";
    recalcular();
  });
  total.addEventListener("input", () => {
    registro.base = "total";
    recalcular();
  });
  producto.addEventListener("change", recalcular);
  tablaProductos.append(fila);
  filasProductos.push(registro);
  return registro;
}

// ---------- Mostrar la orden ----------

function marcarCambios() {
  hayCambiosSinGuardar = true;
}
formOrden.addEventListener("input", marcarCambios);

function boton(texto, nombreIcono, alHacerClic, secundario = true) {
  const b = el("button", { type: "button", className: secundario ? "boton boton-secundario" : "boton", onclick: alHacerClic });
  b.innerHTML = icono(nombreIcono, 16);
  b.append(texto);
  return b;
}

function mostrarAcciones() {
  const acciones = document.getElementById("acciones");
  acciones.replaceChildren();
  if (!orden) return;
  const sinMovimientos = !orden.movimientos?.length;
  acciones.append(boton("Imprimir", "descarga", imprimir));
  if (orden.estado === "pendiente") {
    acciones.append(boton("Anular", "archivo", () => cambiarEstado("anular", "¿Anular esta orden? (no se hizo la aplicación)")));
    if (sinMovimientos) acciones.append(boton("Eliminar", "basura", eliminar));
    acciones.append(boton("Marcar realizada", "check", abrirRealizar, false));
  } else if (orden.estado === "realizada") {
    acciones.append(boton("Volver a pendiente", "historial", () =>
      cambiarEstado("pendiente", "¿Volver la orden a pendiente? Se DEVUELVE al stock lo que se descontó (queda anotado en Movimientos).")));
  } else {
    acciones.append(boton("Reactivar", "refrescar", () => cambiarEstado("reactivar", "¿Reactivar la orden? Vuelve a quedar pendiente.")));
    if (sinMovimientos) acciones.append(boton("Eliminar", "basura", eliminar));
  }
}

function mostrarAvisos() {
  const advertencias = document.getElementById("advertencias");
  advertencias.hidden = !orden?.advertencias.length;
  advertencias.replaceChildren(...(orden?.advertencias || []).map((a) => el("div", {}, `⚠️ ${a}`)));

  const sinVincular = document.getElementById("sin-vincular");
  sinVincular.hidden = !orden;
  if (!orden) return;
  const partes = [];
  if (orden.lotes_mapa.length) partes.push(`Se anota en la ficha de: ${orden.lotes_mapa.map((l) => l.nombre).join(", ")}.`);
  if (orden.lotes_sin_vincular.length) {
    partes.push(`No están en el mapa${orden.campo ? ` (campo ${orden.campo})` : ""}: ${orden.lotes_sin_vincular.join(", ")}. ` +
      "Cuando los cargues (o importes) con ese campo y número, se vinculan solos.");
  }
  sinVincular.textContent = partes.join(" ");
  sinVincular.hidden = partes.length === 0;
}

function mostrarMovimientos() {
  const tarjeta = document.getElementById("tarjeta-movimientos");
  const movimientos = orden?.movimientos || [];
  tarjeta.hidden = movimientos.length === 0;
  document.getElementById("tabla-movimientos").replaceChildren(
    ...movimientos.map((m) =>
      el("tr", {}, el("td", {}, formatearFechaHora(m.fecha)), el("td", {}, pill(m.tipo === "salida" ? "Salida" : "Entrada (devolución)", m.tipo === "salida" ? "ambar" : "verde")),
        el("td", {}, m.insumo_nombre), el("td", { className: "numero" }, `${formatearCantidad(m.cantidad)} ${m.unidad}`), el("td", { className: "suave chico" }, m.motivo))),
  );
}

function mostrarOrden() {
  const nueva = !orden;
  document.getElementById("titulo").textContent = nueva ? "Nueva orden de trabajo" : `Orden ${orden.numero || `#${orden.id}`}`;
  document.title = `${nueva ? "Nueva orden" : `OT ${orden.numero || orden.id}`} · AgroApp`;
  const subtitulo = document.getElementById("subtitulo");
  subtitulo.replaceChildren();
  if (!nueva) {
    subtitulo.append(pill(opciones.estados_orden[orden.estado], COLOR_ESTADO[orden.estado]));
    if (orden.fecha_realizacion) subtitulo.append(` Realizada el ${formatearFecha(orden.fecha_realizacion)}`);
  }
  // Solo una orden pendiente (o nueva) se puede editar.
  const editable = nueva || orden.estado === "pendiente";
  camposOrden.disabled = !editable;
  document.getElementById("pie-guardar").hidden = !editable;
  mostrarAcciones();
  mostrarAvisos();
  mostrarMovimientos();
  // La vista de impresión, al pie (solo de una orden guardada).
  document.getElementById("tarjeta-hoja").hidden = nueva;
  if (!nueva) armarHoja();
}

function completar(datos) {
  formOrden.reset();
  completarFormulario(formOrden, {
    ...datos,
    caldo_ha: numeroParaCampo(datos.caldo_ha),
    campania_id: datos.campania_id ?? "",
    tancadas: datos.tancadas ?? "",
  });
  tablaLotes.replaceChildren();
  tablaProductos.replaceChildren();
  filasLotes = [];
  filasProductos = [];
  for (const l of datos.lotes || []) agregarLote(l);
  for (const p of datos.productos || []) agregarProducto(p);
  if (!filasLotes.length) agregarLote();
  if (!filasProductos.length) agregarProducto();
  recalcular();
  hayCambiosSinGuardar = false;
}

// ---------- Guardar ----------

function armarDatos() {
  const datos = leerFormulario(formOrden);
  const errores = [];
  const lotes = [];
  for (const f of filasLotes) {
    const nombre = f.lote.value.trim();
    const hectareas = leerNumero(f.hectareas.value);
    if (!nombre && !f.hectareas.value.trim()) continue; // Fila vacía: se ignora.
    if (!nombre || !hectareas) errores.push(`El lote «${nombre || "sin nombre"}» necesita nombre y hectáreas.`);
    else lotes.push({ lote: nombre, hectareas });
  }
  const productos = [];
  for (const f of filasProductos) {
    const total = leerNumero(f.total.value);
    if (!f.producto.value && !f.total.value.trim() && !f.dosis.value.trim()) continue;
    if (!f.producto.value) errores.push("Hay una fila de producto sin elegir el producto.");
    else if (!total) errores.push(`Falta la dosis o el total de ${insumoDe(f.producto.value)?.nombre ?? "un producto"}.`);
    else productos.push({ insumo_id: Number(f.producto.value), cantidad_total: total });
  }
  if (!datos.fecha_emision) errores.push("Falta la fecha de emisión.");
  const caldo = datos.caldo_ha ? leerNumero(datos.caldo_ha) : null;
  if (datos.caldo_ha && caldo === null) errores.push("El caldo por hectárea no es un número.");
  return {
    errores,
    datos: {
      ...datos,
      campania_id: datos.campania_id ? Number(datos.campania_id) : null,
      caldo_ha: caldo,
      tancadas: tancadas(),
      lotes,
      productos,
    },
  };
}

formOrden.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const { errores, datos } = armarDatos();
  const mensaje = formOrden.querySelector(":scope > .mensaje");
  if (errores.length) {
    mostrarMensaje(mensaje, `⚠️ ${errores.join(" ")}`, "error");
    return;
  }
  const guardada = await enviarFormulario(formOrden, () => (ordenId ? api("PUT", `/ordenes/${ordenId}`, datos) : api("POST", "/ordenes", datos)));
  if (!guardada) return;
  const eraNueva = !ordenId;
  ordenId = guardada.id;
  if (eraNueva) history.replaceState(null, "", `orden.html?id=${ordenId}`);
  await cargar();
  avisar(guardada.advertencias.length ? "Orden guardada, pero falta stock: mirá el aviso amarillo." : "✅ Orden guardada.", guardada.advertencias.length ? "error" : "ok");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ---------- Acciones ----------

function hayQueGuardarPrimero() {
  if (!hayCambiosSinGuardar) return false;
  avisar("Tenés cambios sin guardar: tocá «Guardar orden» primero.", "error");
  return true;
}

function abrirRealizar() {
  if (hayQueGuardarPrimero()) return;
  formRealizar.reset();
  formRealizar.elements.fecha_realizacion.value = hoyISO();
  document.getElementById("realizar-detalle").textContent =
    "Se descuenta del stock: " + orden.productos.map((p) => `${p.insumo} ${formatearCantidad(p.cantidad_total)} ${p.unidad}`).join(" · ") +
    ". Si a alguno no le alcanza, no se descuenta ninguno.";
  abrirVentana(ventanaRealizar);
}

formRealizar.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const hecha = await enviarFormulario(formRealizar, (datos) => api("POST", `/ordenes/${ordenId}/realizar`, datos));
  if (!hecha) return;
  ventanaRealizar.close();
  avisar("✅ Orden realizada: los productos salieron del stock.");
  cargar();
});

async function cambiarEstado(accion, pregunta) {
  if (hayQueGuardarPrimero()) return;
  if (!confirmar(pregunta)) return;
  try {
    await api("POST", `/ordenes/${ordenId}/${accion}`);
    avisar("✅ Listo.");
  } catch (error) {
    avisar(error.message, "error");
  }
  cargar();
}

async function eliminar() {
  if (!confirmar("¿Eliminar esta orden? No se puede deshacer.")) return;
  try {
    await api("DELETE", `/ordenes/${ordenId}`);
    location.href = "ordenes.html";
  } catch (error) {
    avisar(error.estado === 409 ? "Esta orden ya movió stock: no se puede eliminar (anulala)." : error.message, "error");
  }
}

// ---------- Imprimir: la hoja con la forma de la planilla ----------

function celda(texto, clase = "") {
  return el("td", { className: clase }, texto ?? "");
}

function armarHoja() {
  const o = orden;
  const hectareas = o.hectareas || 0;
  const nTancadas = o.tancadas || null;
  const operarios = o.operarios.split(",").map((t) => t.trim()).filter(Boolean);
  const datos = [
    ["Campaña", o.campania || ""], ["O.T. N°", o.numero], ["Campo", o.campo],
    ["Tarea", opciones.tareas_orden[o.tarea]], ["Máquina", o.maquina],
    ...[0, 1, 2, 3].map((i) => [`Operario ${i + 1}`, operarios[i] || ""]),
    ["F. de emisión", formatearFecha(o.fecha_emision)], ["F. de realización", formatearFecha(o.fecha_realizacion)],
    ["Estado lote", o.estado_lote], ["Cultivo", o.cultivo],
  ];
  const tablaDatos = el("table", { className: "hoja-datos" }, el("tbody", {}, datos.map(([a, b]) => el("tr", {}, el("th", {}, a), celda(b)))));

  const tablaLotesHoja = el(
    "table",
    { className: "hoja-lotes" },
    el("tbody", {},
      el("tr", {}, el("th", {}, "Lts caldo/ha"), celda(o.caldo_ha !== null ? formatearCantidad(o.caldo_ha) : "", "numero"), celda("")),
      el("tr", {}, el("th", {}, "Cant. tancadas"), celda(nTancadas ?? "", "numero"), celda("")),
      el("tr", {}, el("th", {}, "Has/tancada"), celda(nTancadas ? formatearCantidad(hectareas / nTancadas) : "", "numero"), celda("")),
      el("tr", {}, el("th", {}, "Lotes a aplicar"), celda(formatearCantidad(hectareas), "numero fuerte"), celda("Has")),
      o.lotes.map((l) => el("tr", {}, el("th", {}, "Lote"), celda(l.lote), celda(`${formatearCantidad(l.hectareas)} Has`, "numero")))),
  );

  // Productos: agua primero, como en la planilla.
  const filas = [];
  const sumaProductos = o.productos.reduce((s, p) => s + p.cantidad_total, 0);
  const caldo = o.caldo_ha && hectareas ? o.caldo_ha * hectareas : null;
  if (caldo !== null) {
    const agua = Math.max(caldo - sumaProductos, 0);
    filas.push(["Agua", agua / hectareas, nTancadas ? agua / nTancadas : null, agua, "l"]);
  }
  const abreviar = (unidad) => ({ litros: "l" })[unidad] || unidad; // Como en la planilla: "l", "kg".
  for (const p of o.productos) filas.push([p.insumo, p.dosis_ha, p.por_tancada, p.cantidad_total, abreviar(p.unidad)]);
  const tablaProductosHoja = el(
    "table",
    { className: "hoja-productos" },
    el("thead", {}, el("tr", {}, el("th", {}, "N°"), el("th", {}, "Productos"), el("th", {}, "Dosis/ha"), el("th", {}, "Tancada"), el("th", {}, "Consumo total"))),
    el("tbody", {}, filas.map(([nombre, dosis, tancada, total, unidad], i) =>
      el("tr", {}, celda(`${i + 1}-`), celda(nombre), celda(dosis !== null ? `${numeroParaCampo(dosis)} ${unidad}` : "", "numero"),
        celda(tancada !== null ? `${numeroParaCampo(tancada)} ${unidad}` : "", "numero"), celda(`${numeroParaCampo(total)} ${unidad}`, "numero fuerte")))),
    caldo !== null
      ? el("tfoot", {}, el("tr", {}, celda(""), celda("Total caldo", "fuerte"), celda(`${numeroParaCampo(o.caldo_ha)} l`, "numero"),
          celda(nTancadas ? `${numeroParaCampo(caldo / nTancadas)} l` : "", "numero"), celda(`${numeroParaCampo(caldo)} l`, "numero fuerte")))
      : null,
  );

  const titulo = (opciones.tareas_orden[o.tarea] || "Orden de trabajo").toUpperCase();
  document.getElementById("hoja").replaceChildren(
    el("h2", { className: "hoja-titulo" }, titulo),
    el("div", { className: "hoja-descripcion" }, o.descripcion || " "),
    el("div", { className: "hoja-cuerpo" }, tablaDatos, tablaLotesHoja, tablaProductosHoja),
  );
}

function imprimir() {
  if (hayQueGuardarPrimero()) return;
  armarHoja();
  window.print();
}

// ---------- Cargar ----------

async function cargar() {
  try {
    if (ordenId) {
      orden = await api("GET", `/ordenes/${ordenId}`);
      completar(orden);
    } else {
      orden = null;
    }
    mostrarOrden();
  } catch (error) {
    document.getElementById("titulo").textContent = error.estado === 404 ? "No existe esa orden" : `⚠️ ${error.message}`;
  }
}

async function iniciar() {
  opciones = await cargarOpciones();
  const [campanias, todosInsumos, lotes, maquinas, cultivos, siguiente] = await Promise.all([
    api("GET", "/campanias"),
    api("GET", "/insumos?incluir_archivados=true"),
    api("GET", "/lotes"),
    api("GET", "/maquinas"),
    api("GET", "/cultivos"),
    api("GET", "/ordenes/siguiente-numero"),
  ]);
  insumos = todosInsumos.filter((i) => i.hoja !== "repuestos");
  llenarSelectLista(formOrden.elements.campania_id, campanias, (c) => c.nombre, "Sin campaña");
  llenarSelect(formOrden.elements.tarea, opciones.tareas_orden);
  const unicos = (lista) => [...new Set(lista.filter(Boolean))].sort((a, b) => a.localeCompare(b, "es"));
  document.getElementById("lista-campos").replaceChildren(...unicos(lotes.map((l) => l.campo)).map((c) => el("option", { value: c })));
  document.getElementById("lista-maquinas").replaceChildren(...maquinas.map((m) => el("option", { value: m.nombre })));
  document.getElementById("lista-cultivos").replaceChildren(...cultivos.map((c) => el("option", { value: c.nombre })));

  document.getElementById("agregar-lote").addEventListener("click", () => {
    agregarLote().lote.focus();
    marcarCambios();
  });
  document.getElementById("agregar-producto").addEventListener("click", () => {
    agregarProducto().producto.focus();
    marcarCambios();
  });
  formOrden.elements.caldo_ha.addEventListener("input", recalcular);
  formOrden.elements.tancadas.addEventListener("input", recalcular);

  if (ordenId) {
    await cargar();
  } else {
    // Orden nueva: número siguiente, hoy, la campaña que venís mirando y pulverización terrestre.
    completar({
      numero: siguiente.numero,
      fecha_emision: hoyISO(),
      campania_id: campaniaRecordada(campanias)?.id ?? "",
      tarea: "pulverizacion_terrestre",
    });
    mostrarOrden();
  }
}

iniciar();
