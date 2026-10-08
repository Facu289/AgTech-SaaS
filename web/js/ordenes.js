// =========================================================
// ordenes.js — listado de órdenes de trabajo, con filtros y Excel.
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");

let opciones = null;
let ordenes = [];
let ultimasVisibles = [];

const COLOR_ESTADO = { pendiente: "ambar", realizada: "verde", anulada: "gris" };

function textoLotes(orden) {
  return orden.lotes.map((l) => l.lote).join(", ");
}

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const buscado = normalizar(filtros.texto);
  const visibles = ordenes.filter(
    (o) =>
      (!filtros.estado || o.estado === filtros.estado) &&
      (!filtros.campania || String(o.campania_id) === filtros.campania) &&
      (!buscado || normalizar(`${o.numero} ${o.campo} ${textoLotes(o)} ${o.maquina} ${o.operarios} ${o.productos.map((p) => p.insumo).join(" ")}`).includes(buscado)),
  );
  ultimasVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) cuerpoTabla.append(filaVacia(9, ordenes.length ? "Ninguna orden coincide." : "Todavía no hay órdenes. Tocá «Nueva orden»."));
  for (const o of visibles) {
    const estadoCelda = el("td", {}, pill(opciones.estados_orden[o.estado], COLOR_ESTADO[o.estado]));
    if (o.advertencias.length) estadoCelda.append(" ", pill("⚠ Falta stock", "rojo"));
    cuerpoTabla.append(
      el(
        "tr",
        { className: o.estado === "anulada" ? "fila-archivada" : "" },
        el("td", { className: "fuerte", style: "white-space:nowrap" }, el("a", { href: `orden.html?id=${o.id}` }, o.numero || `#${o.id}`)),
        el("td", { style: "white-space:nowrap" }, formatearFecha(o.fecha_emision)),
        el("td", {}, o.campo || "—"),
        el("td", {}, opciones.tareas_orden[o.tarea] || o.tarea),
        el("td", {}, textoLotes(o) || "—"),
        el("td", { className: "numero" }, formatearCantidad(o.hectareas)),
        el("td", { className: "suave chico" }, o.productos.map((p) => p.insumo).join(" · ") || "—"),
        estadoCelda,
        el("td", {}, el("div", { className: "acciones-fila" }, Object.assign(botonIcono("ojo", "Abrir", {}, "a"), { href: `orden.html?id=${o.id}` }))),
      ),
    );
  }
  const pendientes = ordenes.filter((o) => o.estado === "pendiente").length;
  estado.textContent = `${textoActualizado(ordenes.length, "orden", "órdenes")} · ${pendientes} pendiente${pendientes === 1 ? "" : "s"}`;
}

async function cargar() {
  try {
    ordenes = await api("GET", "/ordenes");
    mostrarTabla();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

document.getElementById("boton-nueva").before(
  botonExportar(() =>
    exportarExcel(
      "ordenes_de_trabajo",
      "Órdenes de trabajo",
      ["N°", "Emisión", "Realizada", "Estado", "Campo", "Tarea", "Lotes", "Hectáreas", "Productos"],
      ultimasVisibles.map((o) => [
        o.numero, o.fecha_emision, o.fecha_realizacion, opciones.estados_orden[o.estado], o.campo,
        opciones.tareas_orden[o.tarea], textoLotes(o), o.hectareas,
        o.productos.map((p) => `${p.insumo}: ${formatearCantidad(p.cantidad_total)} ${p.unidad}`).join(" · "),
      ]),
    ),
  ),
);

formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrarTabla));

async function iniciar() {
  opciones = await cargarOpciones();
  llenarSelect(formFiltros.querySelector("[data-estados]"), opciones.estados_orden, "Todos los estados");
  llenarSelectLista(formFiltros.querySelector("[data-campanias]"), await api("GET", "/campanias"), (c) => c.nombre, "Todas las campañas");
  leerFiltrosDeUrl(formFiltros);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
