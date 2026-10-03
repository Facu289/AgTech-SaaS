// =========================================================
// insumos.js — páginas "Insumos" (insumos.html), "Químicos" (quimicos.html)
// y "Repuestos" (repuestos.html).
// Es el mismo código: data-pagina del <body> dice cuál es.
// =========================================================

const PAGINA = document.body.dataset.pagina; // "insumos", "quimicos" o "repuestos"
const ES_REPUESTOS = PAGINA === "repuestos";
const NOMBRE = { insumos: "insumo", quimicos: "químico", repuestos: "repuesto" }[PAGINA];
const TITULO = NOMBRE.charAt(0).toUpperCase() + NOMBRE.slice(1); // "Químico"

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formMovimiento = document.getElementById("form-movimiento");
const selectInsumo = document.getElementById("movimiento-insumo");
const formNuevo = document.getElementById("form-nuevo");
const formFiltros = document.getElementById("filtros");
const ventanaEditar = document.getElementById("ventana-editar");
const formEditar = document.getElementById("form-editar");

let opciones = null; // Categorías, tipos, unidades (vienen de GET /opciones).
let maquinas = []; // Para elegir para qué máquinas sirve un repuesto.
let todos = []; // Todos los insumos de esta página (sin filtrar).
let editandoId = null;
let ultimasVisibles = []; // Lo que se ve en la tabla (para exportar a Excel).

// ¿Este insumo va en esta página? La API ya dice su "hoja" (sale de la categoría).
function correspondeAPagina(insumo) {
  return insumo.hoja === PAGINA;
}

function stockBajo(insumo) {
  return insumo.stock_minimo > 0 && insumo.cantidad <= insumo.stock_minimo;
}

// ---------- Desplegables ----------

// Solo las categorías de esta página (Químicos: agroquímicos; Insumos: el resto...).
// Cuáles van en cada página se define en app/nucleo/opciones.py (CATEGORIAS_QUIMICOS).
function categoriasDeLaPagina() {
  const deEstaPagina = opciones.hojas_insumos[PAGINA];
  return Object.fromEntries(Object.entries(opciones.categorias).filter(([valor]) => deEstaPagina.includes(valor)));
}

// Los tipos (subcategorías) dependen de la categoría elegida.
function subcategoriasDe(categoria) {
  return opciones.subcategorias[categoria] || {};
}

// Todos los tipos de las categorías de esta página (para el filtro sin categoría elegida).
function todasLasSubcategorias() {
  const todas = {};
  for (const categoria of Object.keys(categoriasDeLaPagina())) {
    Object.assign(todas, subcategoriasDe(categoria));
  }
  return todas;
}

function actualizarTipos(formulario) {
  const categoria = formulario.elements.categoria.value;
  const select = formulario.querySelector("[data-subcategorias]");
  const tipos = subcategoriasDe(categoria);
  llenarSelect(select, tipos, Object.keys(tipos).length ? "Sin especificar" : "—");
  select.disabled = Object.keys(tipos).length === 0;
  // La máquina solo tiene sentido para repuestos.
  const campoMaquina = formulario.querySelector("[data-solo-repuesto]");
  if (campoMaquina) campoMaquina.hidden = categoria !== "repuesto";
}

function prepararDesplegables() {
  for (const select of document.querySelectorAll("[data-unidades]")) {
    llenarSelect(select, opciones.unidades, "Elegí…");
  }
  // En el formulario de edición se puede cambiar a cualquier categoría (incluso repuesto).
  llenarSelect(formEditar.elements.categoria, opciones.categorias, "Elegí…");
  const selectCategoriaNuevo = formNuevo.querySelector("[data-categorias]");
  // Si la página tiene una sola categoría (Químicos = Agroquímico), ya queda elegida.
  const unaSola = Object.keys(categoriasDeLaPagina()).length === 1;
  if (selectCategoriaNuevo) llenarSelect(selectCategoriaNuevo, categoriasDeLaPagina(), unaSola ? "" : "Elegí…");

  const filtroCategoria = formFiltros.querySelector("[data-categorias-filtro]");
  if (filtroCategoria) llenarSelect(filtroCategoria, categoriasDeLaPagina(), "Todas las categorías");
  actualizarFiltroTipos();

  actualizarTipos(formNuevo);
  for (const formulario of [formNuevo, formEditar]) {
    formulario.elements.categoria.addEventListener("change", () => actualizarTipos(formulario));
  }
}

function actualizarFiltroTipos() {
  const select = formFiltros.querySelector("[data-subcategorias-filtro]");
  const categoria = formFiltros.elements.categoria?.value;
  const tipos = categoria ? subcategoriasDe(categoria) : ES_REPUESTOS ? subcategoriasDe("repuesto") : todasLasSubcategorias();
  llenarSelect(select, tipos, "Todos los tipos");
}

function llenarSelectMaquinas() {
  const lista = Object.fromEntries(maquinas.map((m) => [m.id, m.nombre]));
  for (const selector of document.querySelectorAll("details[data-maquinas]")) {
    llenarSelectorMultiple(selector, lista);
  }
  const filtro = formFiltros.querySelector("[data-maquinas-filtro]");
  if (filtro) {
    llenarSelect(filtro, { general: "Generales (sin máquina)", ...lista }, "Todas las máquinas");
  }
}

// El desplegable de "Registrar movimiento": solo los de esta página, sin archivados.
function llenarSelectInsumos() {
  const activos = todos
    .filter((i) => !i.archivado)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const lista = Object.fromEntries(
    activos.map((i) => [i.id, `${i.nombre} — ${formatearCantidad(i.cantidad)} ${i.unidad}`]),
  );
  llenarSelect(selectInsumo, lista, "Elegí…");
}

// ---------- Alertas ----------

function mostrarAlertas() {
  const contenedor = document.getElementById("alertas");
  contenedor.replaceChildren();
  const bajos = todos.filter((i) => !i.archivado && stockBajo(i));
  if (bajos.length === 0) return;
  const alerta = el("div", { className: "alerta", role: "status" });
  alerta.innerHTML = icono("alerta");
  alerta.append(
    el(
      "div",
      {},
      `${bajos.length} ${bajos.length === 1 ? NOMBRE : NOMBRE + "s"} en o por debajo del stock mínimo:`,
      el("ul", {}, bajos.map((i) => el("li", {}, `${i.nombre}: ${formatearCantidad(i.cantidad)} ${i.unidad} (mínimo ${formatearCantidad(i.stock_minimo)})`))),
    ),
  );
  contenedor.append(alerta);
}

// ---------- Tabla con filtros ----------

function leerFiltros() {
  return leerFormulario(formFiltros);
}

function pasaFiltros(insumo, filtros) {
  if (!filtros.archivados && insumo.archivado) return false;
  if (filtros.texto && !normalizar(insumo.nombre).includes(normalizar(filtros.texto))) return false;
  if (filtros.categoria && insumo.categoria !== filtros.categoria) return false;
  if (filtros.subcategoria && insumo.subcategoria !== filtros.subcategoria) return false;
  if (filtros.maquina === "general" && insumo.maquinas.length > 0) return false;
  if (filtros.maquina && filtros.maquina !== "general" && !insumo.maquinas.some((m) => String(m.id) === filtros.maquina)) return false;
  if (filtros.stock === "con" && insumo.cantidad <= 0) return false;
  if (filtros.stock === "sin" && insumo.cantidad > 0) return false;
  if (filtros.stock === "bajo" && !stockBajo(insumo)) return false;
  return true;
}

function celdaCategoria(insumo) {
  const celda = el("td");
  if (ES_REPUESTOS) {
    const tipo = subcategoriasDe("repuesto")[insumo.subcategoria];
    celda.append(tipo ? pillDeOpcion(subcategoriasDe("repuesto"), insumo.subcategoria) : el("span", { className: "suave" }, "—"));
    return celda;
  }
  celda.append(pillDeOpcion(opciones.categorias, insumo.categoria));
  const tipo = subcategoriasDe(insumo.categoria)[insumo.subcategoria];
  if (tipo) celda.append(el("span", { className: "detalle-pill" }, tipo));
  return celda;
}

function botonesFila(insumo) {
  const botones = el("div", { className: "acciones-fila" });
  botones.append(
    botonIcono("historial", "Ver historial de movimientos", { href: `movimientos.html?insumo_id=${insumo.id}` }, "a"),
    botonIcono("lapiz", "Editar", { onclick: () => abrirEdicion(insumo) }),
  );
  if (insumo.archivado) {
    botones.append(botonIcono("archivo", "Desarchivar", { onclick: () => archivar(insumo, false) }));
  } else if (insumo.tiene_movimientos) {
    // Tiene historial: no se borra, se archiva (deja de aparecer pero no se pierde nada).
    botones.append(botonIcono("archivo", "Archivar (tiene historial, no se puede eliminar)", { onclick: () => archivar(insumo, true) }));
  } else {
    botones.append(botonIcono("basura", "Eliminar", { className: "peligro", onclick: () => eliminar(insumo) }));
  }
  return botones;
}

function mostrarTabla() {
  const filtros = leerFiltros();
  guardarFiltrosEnUrl(filtros);
  const visibles = todos.filter((i) => pasaFiltros(i, filtros));
  ultimasVisibles = visibles;
  cuerpoTabla.replaceChildren();

  const columnas = ES_REPUESTOS ? 7 : 6;
  if (visibles.length === 0) {
    const hayFiltros = Object.values(filtros).some((v) => v !== "" && v !== false);
    cuerpoTabla.append(filaVacia(columnas, hayFiltros ? "Ningún dato coincide con los filtros." : `Todavía no hay ${NOMBRE}s cargados.`));
  }

  for (const insumo of visibles) {
    const bajo = stockBajo(insumo);
    const claseCantidad = `numero${insumo.cantidad === 0 || bajo ? " sin-stock" : ""}`;
    const nombre = el("td", { className: "fuerte" }, insumo.nombre);
    if (insumo.archivado) nombre.append(" ", pill("Archivado", "gris"));

    const fila = el(
      "tr",
      { className: insumo.archivado ? "fila-archivada" : "" },
      nombre,
      celdaCategoria(insumo),
      ES_REPUESTOS
        ? el("td", {}, insumo.maquinas.length ? insumo.maquinas.map((m) => m.nombre).join(", ") : el("span", { className: "suave" }, "General"))
        : null,
      el("td", { className: claseCantidad, title: bajo ? "En o por debajo del mínimo" : "" }, formatearCantidad(insumo.cantidad)),
      el("td", { className: "suave" }, insumo.unidad),
      el("td", { className: "numero suave" }, insumo.stock_minimo > 0 ? formatearCantidad(insumo.stock_minimo) : "—"),
      el("td", {}, botonesFila(insumo)),
    );
    cuerpoTabla.append(fila);
  }

  const total = todos.filter((i) => filtros.archivados || !i.archivado).length;
  const filtrado = visibles.length === total ? "" : ` (mostrando ${visibles.length})`;
  estado.textContent = textoActualizado(total, NOMBRE, NOMBRE + "s") + filtrado;
}

// ---------- Cargar datos ----------

async function cargarInsumos() {
  try {
    // Pedimos también los archivados; el filtro decide si se ven.
    const insumos = await api("GET", "/insumos?incluir_archivados=true");
    todos = insumos.filter(correspondeAPagina);
    mostrarTabla();
    llenarSelectInsumos();
    mostrarAlertas();
    estado.classList.remove("error");
  } catch (error) {
    estado.textContent = `⚠️ No se pudo cargar el stock: ${error.message}`;
  }
}

async function cargarMaquinas() {
  try {
    maquinas = await api("GET", "/maquinas");
  } catch {
    maquinas = [];
  }
  llenarSelectMaquinas();
}

// ---------- Acciones ----------

formMovimiento.addEventListener("submit", async (evento) => {
  evento.preventDefault(); // Que no recargue la página: mandamos los datos con fetch.
  const insumo = await enviarFormulario(formMovimiento, (datos) =>
    api("POST", `/insumos/${datos.insumo_id}/movimientos`, {
      tipo: datos.tipo,
      cantidad: datos.cantidad, // Texto tal cual ("2,5"): la API lo interpreta.
      motivo: datos.motivo || "Web",
    }),
  );
  if (!insumo) return;
  const tipo = formMovimiento.elements.tipo.value === "entrada" ? "Entrada" : "Salida";
  avisar(`✅ ${tipo} registrada en ${insumo.nombre}. Stock actual: ${formatearCantidad(insumo.cantidad)} ${insumo.unidad}`);
  formMovimiento.elements.cantidad.value = "";
  formMovimiento.elements.motivo.value = "";
  formMovimiento.elements.cantidad.focus();
  cargarInsumos();
});

formNuevo.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const creado = await enviarFormulario(formNuevo, (datos) => api("POST", "/insumos", datos));
  if (!creado) return;
  avisar(`✅ ${TITULO} creado: ${creado.nombre}. Cargale stock con "Registrar movimiento".`);
  formNuevo.reset();
  actualizarTipos(formNuevo);
  formNuevo.elements.nombre.focus();
  await cargarInsumos();
  selectInsumo.value = creado.id; // Listo para cargarle stock.
});

function abrirEdicion(insumo) {
  editandoId = insumo.id;
  formEditar.elements.categoria.value = insumo.categoria;
  actualizarTipos(formEditar);
  completarFormulario(formEditar, { ...insumo, maquinas: insumo.maquinas.map((m) => m.id) });
  abrirVentana(ventanaEditar);
}

formEditar.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formEditar, (datos) => api("PUT", `/insumos/${editandoId}`, datos));
  if (!guardado) return;
  ventanaEditar.close();
  avisar(`✅ Cambios guardados en ${guardado.nombre}.`);
  cargarInsumos();
});

async function archivar(insumo, archivar) {
  if (archivar && !confirmar(`¿Archivar "${insumo.nombre}"?\nDeja de aparecer en el stock y en Telegram, pero su historial se conserva.`)) return;
  try {
    await api("POST", `/insumos/${insumo.id}/${archivar ? "archivar" : "desarchivar"}`);
    avisar(archivar ? `Archivado: ${insumo.nombre}` : `Desarchivado: ${insumo.nombre}`);
    cargarInsumos();
  } catch (error) {
    avisar(error.message, "error");
  }
}

async function eliminar(insumo) {
  if (!confirmar(`¿Eliminar "${insumo.nombre}"? No se puede deshacer.`)) return;
  try {
    await api("DELETE", `/insumos/${insumo.id}`);
    avisar(`Eliminado: ${insumo.nombre}`);
    cargarInsumos();
  } catch (error) {
    avisar(error.message, "error");
  }
}

// Filtros: se aplican al instante, mientras escribís o elegís.
formFiltros.addEventListener("input", (evento) => {
  if (evento.target.name === "categoria") actualizarFiltroTipos();
  mostrarTabla();
});
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => {
  setTimeout(() => {
    actualizarFiltroTipos();
    mostrarTabla();
  }); // Esperamos a que el navegador vacíe los campos.
});

// Exportar a Excel exactamente lo que se ve (con los filtros aplicados).
function exportar() {
  const columnas = ES_REPUESTOS
    ? ["Repuesto", "Tipo", "Máquinas", "Cantidad", "Unidad", "Stock mínimo", "Archivado"]
    : [TITULO, "Categoría", "Tipo", "Cantidad", "Unidad", "Stock mínimo", "Archivado"];
  const filas = ultimasVisibles.map((i) => {
    const tipo = subcategoriasDe(i.categoria)[i.subcategoria] || "";
    const nombresMaquinas = i.maquinas.map((m) => m.nombre).join(", ") || "General";
    const inicio = ES_REPUESTOS ? [i.nombre, tipo, nombresMaquinas] : [i.nombre, opciones.categorias[i.categoria], tipo];
    return [...inicio, i.cantidad, i.unidad, i.stock_minimo, i.archivado ? "Sí" : "No"];
  });
  exportarExcel(PAGINA, opciones.hojas_titulos[PAGINA], columnas, filas);
}
document.getElementById("boton-actualizar").before(botonExportar(exportar));

document.getElementById("boton-actualizar").addEventListener("click", () => {
  cargarInsumos();
  cargarMaquinas();
});

// ---------- Inicio ----------

async function iniciar() {
  try {
    opciones = await cargarOpciones();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  prepararDesplegables();
  leerFiltrosDeUrl(formFiltros);
  actualizarFiltroTipos();
  leerFiltrosDeUrl(formFiltros); // Otra vez: el tipo depende de la categoría.
  await cargarMaquinas();
  await cargarInsumos();
  refrescarAutomaticamente(cargarInsumos);
}

iniciar();
