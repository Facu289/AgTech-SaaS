// =========================================================
// comun-lotes.js — lo que comparten Inicio, Lotes, la ficha de un lote y Cultivos:
// el mapa satelital, los colores por cultivo, la leyenda y las ventanas de
// "nueva campaña" y "cultivo del lote".
// Se carga después de comun.js (y de Leaflet, en las páginas con mapa).
// =========================================================

// ---------- Mapa satelital ----------

// Fotos satelitales de Esri (gratis, sin clave). OJO: en estos links va {y} antes que {x}.
const URL_SATELITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const URL_NOMBRES = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";

// Leaflet viene de internet (CDN). Si no cargó, avisamos en vez de romper toda la página.
function hayMapa(contenedor) {
  if (typeof L !== "undefined") return true;
  contenedor.replaceChildren(el("p", { className: "vacio" }, "No se pudo cargar el mapa (¿hay internet?)."));
  return false;
}

function crearMapaSatelital(contenedor, opcionesMapa = {}) {
  const mapa = L.map(contenedor, opcionesMapa).setView([-31.5, -63.5], 6); // Centro del país.
  L.tileLayer(URL_SATELITE, {
    maxZoom: 20,
    maxNativeZoom: 18, // Más cerca que 18 no hay fotos en el campo: se agranda la de 18.
    attribution: "Imágenes © Esri, Maxar, Earthstar Geographics",
  }).addTo(mapa);
  const nombres = L.tileLayer(URL_NOMBRES, { maxZoom: 20, maxNativeZoom: 18 }).addTo(mapa);
  L.control.layers(null, { "Nombres de lugares": nombres }, { position: "topright" }).addTo(mapa);
  L.control.scale({ imperial: false }).addTo(mapa);
  // Leaflet mide el mapa UNA vez al arrancar. Si después cambia de tamaño (plegar el menú,
  // girar el celular), hay que avisarle; si no, quedan franjas grises.
  new ResizeObserver(() => mapa.invalidateSize()).observe(mapa.getContainer());
  return mapa;
}

// ---------- Colores de cada lote según su cultivo ----------

// Relleno = cultivo de primera. Si hay de segunda, el borde va punteado con su color.
// Sin cultivo cargado: borde amarillo y casi transparente.
function estiloLote(lote, elegido = false) {
  const [primero, segundo] = lote.cultivos || [];
  const relleno = primero?.color;
  return {
    color: elegido ? "#FFFFFF" : segundo?.color || relleno || "#FACC15",
    weight: elegido ? 4 : segundo ? 3 : 2,
    dashArray: segundo ? "8 6" : null,
    fillColor: relleno || "#FFFFFF",
    fillOpacity: relleno ? (elegido ? 0.6 : 0.45) : elegido ? 0.25 : 0.08,
  };
}

// "Trigo → Soja 2ª"
function nombreCultivo(fila) {
  return fila.ciclo === "segunda" ? `${fila.cultivo} 2ª` : fila.cultivo;
}

function textoCultivos(lote) {
  return (lote.cultivos || []).map(nombreCultivo).join(" → ");
}

// Cuadradito del color del cultivo + nombre.
function muestraCultivo(color, texto) {
  return el("span", { className: "cultivo-chip" }, el("span", { className: "cultivo-color", style: `background:${color}` }), texto);
}

// Dibuja los lotes (con forma) en un grupo del mapa. Devuelve Map: id del lote → su polígono.
function dibujarLotes(grupo, lotes, { seleccionado = null, alHacerClic = null } = {}) {
  grupo.clearLayers();
  const capas = new Map();
  // Los más grandes primero: así un lote chico queda encima y se puede tocar.
  const ordenados = [...lotes].sort((a, b) => (b.hectareas || 0) - (a.hectareas || 0));
  for (const lote of ordenados) {
    if (!lote.geometria) continue;
    const capa = L.geoJSON(lote.geometria).getLayers()[0];
    capa.setStyle(estiloLote(lote, lote.id === seleccionado));
    // La etiqueta se arma con el() (texto, no HTML): un nombre raro nunca se ejecuta como código.
    const cultivos = textoCultivos(lote);
    const etiqueta = el("span", {}, el("strong", {}, lote.nombre), cultivos ? el("small", {}, cultivos) : null);
    capa.bindTooltip(etiqueta, { permanent: true, direction: "center", className: "etiqueta-lote" });
    if (alHacerClic) capa.on("click", () => alHacerClic(lote));
    capa.addTo(grupo);
    capas.set(lote.id, capa);
  }
  return capas;
}

// Hectáreas de un cultivo en un lote: las cargadas, o si no, todo el lote.
function hectareasSembradas(fila, lote) {
  return fila.hectareas ?? lote.hectareas ?? 0;
}

// Leyenda: cada cultivo de la campaña con su color y sus hectáreas, y los lotes sin cultivo.
function armarLeyenda(lotes) {
  const porCultivo = new Map();
  let sinCultivo = 0;
  for (const lote of lotes) {
    if (!lote.cultivos?.length) sinCultivo += lote.hectareas || 0;
    for (const fila of lote.cultivos || []) {
      const clave = nombreCultivo(fila);
      const actual = porCultivo.get(clave) || { color: fila.color, hectareas: 0 };
      actual.hectareas += hectareasSembradas(fila, lote);
      porCultivo.set(clave, actual);
    }
  }
  const items = [...porCultivo].sort((a, b) => b[1].hectareas - a[1].hectareas);
  const lista = el("ul", { className: "leyenda" });
  for (const [nombre, dato] of items) {
    lista.append(el("li", {}, muestraCultivo(dato.color, nombre), el("span", { className: "suave" }, `${formatearCantidad(dato.hectareas)} ha`)));
  }
  if (sinCultivo > 0 || items.length === 0) {
    lista.append(el("li", {}, muestraCultivo("transparent", "Sin cultivo"), el("span", { className: "suave" }, `${formatearCantidad(sinCultivo)} ha`)));
  }
  return lista;
}

// ---------- Campaña elegida ----------
// Se recuerda en este navegador la última campaña que miraste (Inicio y Lotes muestran la misma).

const CLAVE_CAMPANIA = "agroapp-campania";

function campaniaRecordada(campanias) {
  let id = null;
  try {
    id = Number(localStorage.getItem(CLAVE_CAMPANIA));
  } catch {
    // Sin localStorage (modo incógnito): se usa la más nueva.
  }
  return campanias.find((c) => c.id === id) || campanias[0] || null;
}

function recordarCampania(id) {
  try {
    localStorage.setItem(CLAVE_CAMPANIA, String(id));
  } catch {
    // No pasa nada: la próxima vez arranca en la más nueva.
  }
}

// La campaña agrícola arranca a mitad de año (siembra de trigo): en octubre de 2026 es "2026/27".
function sugerirNombreCampania(campanias) {
  const hoy = new Date();
  let anio = hoy.getMonth() >= 5 ? hoy.getFullYear() : hoy.getFullYear() - 1;
  const nombre = (a) => `${a}/${String((a + 1) % 100).padStart(2, "0")}`;
  const usados = new Set(campanias.map((c) => c.nombre));
  while (usados.has(nombre(anio))) anio += 1;
  return nombre(anio);
}

// Llena un <select> con una lista de objetos, en el orden de la lista.
// (llenarSelect de comun.js usa un diccionario, y JavaScript ordena solas las claves numéricas.)
function llenarSelectLista(select, lista, texto, primera = "") {
  const elegido = select.value;
  select.replaceChildren();
  if (primera) select.append(el("option", { value: "" }, primera));
  for (const item of lista) select.append(el("option", { value: item.id }, texto(item)));
  if ([...select.options].some((opcion) => opcion.value === elegido)) select.value = elegido;
}

// ---------- Ventanas armadas con JavaScript ----------
// Así la misma ventana sirve en varias páginas sin copiar el HTML en cada una.

function crearVentana(titulo, nombreIcono, ...campos) {
  const formulario = el(
    "form",
    { method: "dialog" },
    el("div", { className: "tarjeta-titulo" }, el("div", { className: "icono-caja", dataset: { icono: nombreIcono } }), el("h2", {}, titulo)),
    el("div", { className: "campos", style: "--columnas: 1fr 1fr" }, ...campos),
    el("p", { className: "mensaje", hidden: true }),
    el(
      "div",
      { className: "ventana-pie" },
      // type="button": así Enter guarda (y no cancela).
      el("button", { className: "boton boton-secundario", type: "button", value: "cancelar" }, "Cancelar"),
      el("button", { className: "boton", type: "submit", dataset: { icono: "check" } }, "Guardar"),
    ),
  );
  const ventana = el("dialog", { className: "ventana" }, formulario);
  document.body.append(ventana);
  ponerIconos(ventana);
  return { ventana, formulario };
}

function campo(texto, control, ancho = false) {
  return el("label", { className: "campo", style: ancho ? "grid-column: 1 / -1" : null }, el("span", {}, texto), control);
}

// Pide el nombre de una campaña nueva y la crea. Devuelve la campaña creada (o null si se canceló).
function pedirCampaniaNueva(campanias) {
  const { ventana, formulario } = crearVentana(
    "Nueva campaña",
    "calendario",
    campo("Nombre", el("input", { name: "nombre", required: true, maxLength: 20, autocomplete: "off", placeholder: "Ej: 2026/27" }), true),
  );
  formulario.elements.nombre.value = sugerirNombreCampania(campanias);
  return new Promise((resolver) => {
    let creada = null;
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      creada = await enviarFormulario(formulario, (datos) => api("POST", "/campanias", datos));
      if (creada) ventana.close();
    });
    ventana.addEventListener("close", () => {
      ventana.remove();
      resolver(creada);
    });
    abrirVentana(ventana);
  });
}

// Agrega (fila = null) o edita qué se sembró en un lote. Devuelve lo guardado (o null).
// campanias y cultivos: las listas de la API. campaniaId: la que se propone para uno nuevo.
function abrirVentanaCultivoLote({ lote, fila = null, campanias, cultivos, campaniaId = null }) {
  const selectCampania = el("select", { name: "campania_id", required: true });
  const selectCultivo = el("select", { name: "cultivo_id", required: true });
  const botonNuevaCampania = el("button", { className: "boton-tabla", type: "button" }, "+ Nueva campaña");
  const hectareasLote = lote.hectareas ? `Todo el lote (${formatearCantidad(lote.hectareas)} ha)` : "Todo el lote";

  const { ventana, formulario } = crearVentana(
    fila ? `${lote.nombre}: editar cultivo` : `${lote.nombre}: agregar cultivo`,
    "hoja",
    el("div", { className: "campo" }, el("span", {}, "Campaña"), el("div", { className: "fila-con-boton" }, selectCampania, botonNuevaCampania)),
    campo("Ciclo", el("select", { name: "ciclo" }, el("option", { value: "primera" }, "Primera"), el("option", { value: "segunda" }, "Segunda (ej: soja después de trigo)"))),
    campo("Cultivo", selectCultivo),
    campo("Variedad / híbrido", el("input", { name: "variedad", maxLength: 80, autocomplete: "off", placeholder: "Ej: DM 46R18" })),
    campo("Fecha de siembra", el("input", { name: "fecha_siembra", type: "date" })),
    campo("Fecha de cosecha", el("input", { name: "fecha_cosecha", type: "date" })),
    campo("Hectáreas sembradas", el("input", { name: "hectareas", inputmode: "decimal", autocomplete: "off", placeholder: hectareasLote })),
    campo("Rinde (qq/ha)", el("input", { name: "rinde", inputmode: "decimal", autocomplete: "off", placeholder: "Al cosechar" })),
    campo("Observaciones", el("textarea", { name: "observaciones", maxLength: 1000 }), true),
  );

  llenarSelectLista(selectCampania, campanias, (c) => c.nombre, campanias.length ? "" : "Creá una campaña →");
  llenarSelectLista(selectCultivo, cultivos, (c) => c.nombre, "Elegí…");
  if (fila) {
    completarFormulario(formulario, { ...fila, hectareas: formatearCantidad(fila.hectareas), rinde: formatearCantidad(fila.rinde) });
  } else {
    selectCampania.value = campaniaId ?? campanias[0]?.id ?? "";
    // Si en esa campaña el lote ya tiene primera, se propone segunda.
    const usados = (lote.cultivos || []).filter((c) => String(c.campania_id) === selectCampania.value).map((c) => c.ciclo);
    formulario.elements.ciclo.value = usados.includes("primera") ? "segunda" : "primera";
  }

  botonNuevaCampania.addEventListener("click", async () => {
    const nueva = await pedirCampaniaNueva(campanias);
    if (!nueva) return;
    campanias.unshift(nueva);
    llenarSelectLista(selectCampania, campanias, (c) => c.nombre);
    selectCampania.value = nueva.id;
  });

  return new Promise((resolver) => {
    let guardado = null;
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      guardado = await enviarFormulario(formulario, (datos) =>
        fila ? api("PUT", `/lote-cultivos/${fila.id}`, datos) : api("POST", `/lotes/${lote.id}/cultivos`, datos),
      );
      if (guardado) ventana.close();
    });
    ventana.addEventListener("close", () => {
      ventana.remove();
      resolver(guardado);
    });
    abrirVentana(ventana);
  });
}
