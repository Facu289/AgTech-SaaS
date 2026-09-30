// =========================================================
// movimientos.js — historial de entradas y salidas de todos los insumos.
// A diferencia de la tabla de stock, acá los filtros se aplican EN EL
// SERVIDOR (GET /movimientos?tipo=...&desde=...), porque con los años
// puede haber miles de movimientos y no conviene traerlos todos.
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");
const totales = document.getElementById("totales");
const LIMITE = 500;

let insumosPorId = {};
let ultimos = []; // Lo que se ve (para exportar).

async function prepararFiltros() {
  const [opciones, insumos] = await Promise.all([
    cargarOpciones(),
    api("GET", "/insumos?incluir_archivados=true"),
  ]);
  insumosPorId = Object.fromEntries(insumos.map((i) => [i.id, i]));
  const ordenados = [...insumos].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  llenarSelect(document.getElementById("filtro-insumo"), Object.fromEntries(ordenados.map((i) => [i.id, i.nombre])), "Todos los insumos");
  llenarSelect(document.getElementById("filtro-categoria"), opciones.categorias, "Todas las categorías");
}

function mostrarTotales(movimientos, filtros) {
  const insumo = insumosPorId[filtros.insumo_id];
  totales.hidden = !insumo;
  if (!insumo) return;
  const suma = (tipo) => movimientos.filter((m) => m.tipo === tipo).reduce((total, m) => total + m.cantidad, 0);
  const dato = (valor, nombre) =>
    el("div", { className: "dato" }, el("div", { className: "dato-valor" }, valor), el("div", { className: "dato-nombre" }, nombre));
  totales.replaceChildren(
    dato(`${formatearCantidad(insumo.cantidad)} ${insumo.unidad}`, `Stock actual de ${insumo.nombre}`),
    dato(`+${formatearCantidad(suma("entrada"))}`, "Entradas (en este período)"),
    dato(`−${formatearCantidad(suma("salida"))}`, "Salidas (en este período)"),
  );
}

async function cargarMovimientos() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  // Armamos la dirección con los filtros que tienen valor: /movimientos?tipo=salida&desde=...
  const parametros = new URLSearchParams({ limite: LIMITE });
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor) parametros.set(clave, valor);
  }

  let movimientos;
  try {
    movimientos = await api("GET", `/movimientos?${parametros}`);
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }

  ultimos = movimientos;
  cuerpoTabla.replaceChildren();
  if (movimientos.length === 0) cuerpoTabla.append(filaVacia(5, "No hay movimientos con esos filtros."));
  for (const m of movimientos) {
    const esEntrada = m.tipo === "entrada";
    cuerpoTabla.append(
      el(
        "tr",
        {},
        el("td", { className: "suave", style: "white-space:nowrap" }, formatearFechaHora(m.fecha)),
        el("td", { className: "fuerte" }, m.insumo_nombre),
        el("td", {}, pill(esEntrada ? "Entrada" : "Salida", esEntrada ? "verde" : "ambar")),
        el("td", { className: "numero" }, `${esEntrada ? "+" : "−"}${formatearCantidad(m.cantidad)} ${m.unidad}`),
        el("td", {}, m.motivo || el("span", { className: "suave" }, "—")),
      ),
    );
  }
  estado.textContent = textoActualizado(movimientos.length, "movimiento", "movimientos");
  document.getElementById("limite").hidden = movimientos.length < LIMITE;
  mostrarTotales(movimientos, filtros);
}

// Al escribir en el buscador esperamos un momento (300 ms) antes de pedir,
// para no hacer un pedido por cada letra. Esto se llama "debounce".
let espera;
formFiltros.addEventListener("input", () => {
  clearTimeout(espera);
  espera = setTimeout(cargarMovimientos, 300);
});
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(cargarMovimientos));
document.getElementById("boton-actualizar").addEventListener("click", cargarMovimientos);
document.getElementById("boton-actualizar").before(
  botonExportar(() =>
    exportarExcel(
      "movimientos",
      "Movimientos",
      ["Fecha", "Insumo", "Tipo", "Cantidad", "Unidad", "Motivo"],
      ultimos.map((m) => [m.fecha, m.insumo_nombre, m.tipo === "entrada" ? "Entrada" : "Salida", m.tipo === "entrada" ? m.cantidad : -m.cantidad, m.unidad, m.motivo]),
    ),
  ),
);

async function iniciar() {
  try {
    await prepararFiltros();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  leerFiltrosDeUrl(formFiltros); // Ej: movimientos.html?insumo_id=3 (desde el botón Historial)
  await cargarMovimientos();
  refrescarAutomaticamente(cargarMovimientos);
}

iniciar();
