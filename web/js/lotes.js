// =========================================================
// lotes.js — los lotes del campo en el mapa satelital, pintados por cultivo.
//
// Piezas:
//   Leaflet   → el mapa (arrastrar, zoom, formas encima). Fondo satelital de Esri.
//   Geoman    → las herramientas para dibujar y editar polígonos.
//   comun-lotes.js → mapa, colores por cultivo, leyenda y ventanas (las comparte con Inicio y la ficha).
// Cada lote viaja a la API como GeoJSON: {type: "Polygon", coordinates: [[[lon, lat], ...]]}.
// =========================================================

const estado = document.getElementById("estado");
const lista = document.getElementById("lista");
const buscar = document.getElementById("buscar");
const verArchivados = document.getElementById("ver-archivados");
const totalHectareas = document.getElementById("total-hectareas");
const selectCampania = document.getElementById("campania");
const leyenda = document.getElementById("leyenda");
const ventana = document.getElementById("ventana-lote");
const formLote = document.getElementById("form-lote");
const ayudaHectareas = document.getElementById("ayuda-hectareas");
const barra = document.getElementById("barra-mapa");
const barraTexto = document.getElementById("barra-texto");
const barraGuardar = document.getElementById("barra-guardar");
const botonNuevo = document.getElementById("boton-nuevo");

let lotes = [];
let campanias = [];
let cultivos = [];
let campania = null; // la campaña que se está mirando (pinta el mapa)
let seleccionado = Number(new URLSearchParams(location.search).get("lote")) || null; // lotes.html?lote=3
let capasPorId = new Map(); // id del lote → su polígono en el mapa

// Lo que se está haciendo en el mapa (null = nada):
//   { tipo: "nuevo" }                 dibujando un lote nuevo
//   { tipo: "dibujar", lote }         dibujando la forma de un lote que no tenía
//   { tipo: "forma", lote, capa }     moviendo los puntos de un lote
let modo = null;
let capaPendiente = null; // el polígono recién dibujado, esperando nombre (lote nuevo)
let ventanaLote = null; // null = la ventana es de un lote nuevo; si no, el lote que se edita
let hectareasSugeridas = ""; // lo que la ventana propuso en "Hectáreas" (para saber si lo cambiaste)

// ---------- Área (hectáreas) ----------
// La MISMA cuenta que app/lotes/geometria.py (si cambiás una, cambiá la otra).
// Se hace acá también para mostrar las hectáreas mientras dibujás, sin esperar al servidor.

const RADIO_ECUADOR = 6378137;
const EXCENTRICIDAD_2 = 0.00669437999014;
const rad = (grados) => (grados * Math.PI) / 180;

function radioLocal2(latitud) {
  const seno = Math.sin(rad(latitud));
  const w2 = 1 - EXCENTRICIDAD_2 * seno * seno;
  const meridiano = (RADIO_ECUADOR * (1 - EXCENTRICIDAD_2)) / w2 ** 1.5;
  const normal = RADIO_ECUADOR / Math.sqrt(w2);
  return meridiano * normal;
}

function areaAnillo(anillo, radio2) {
  const n = anillo.length - 1; // el último punto repite el primero
  if (n < 3) return 0;
  let total = 0;
  for (let i = 0; i < n; i++) {
    const anterior = anillo[i > 0 ? i - 1 : n - 1];
    const siguiente = anillo[i + 1];
    total += (rad(siguiente[0]) - rad(anterior[0])) * Math.sin(rad(anillo[i][1]));
  }
  return Math.abs((total * radio2) / 2);
}

function hectareasDe(geometria) {
  const [borde, ...huecos] = geometria.coordinates;
  const latitudMedia = borde.slice(0, -1).reduce((suma, p) => suma + p[1], 0) / (borde.length - 1);
  const radio2 = radioLocal2(latitudMedia);
  let metros2 = areaAnillo(borde, radio2);
  for (const hueco of huecos) metros2 -= areaAnillo(hueco, radio2);
  return Math.round((Math.max(metros2, 0) / 10000) * 100) / 100;
}

// La geometría GeoJSON de una capa del mapa.
function geometriaDe(capa) {
  return capa.toGeoJSON().geometry;
}

// ¿Las hectáreas guardadas son las del dibujo, o alguien las escribió a mano?
function hectareasAMano(lote) {
  if (lote.hectareas === null) return false;
  if (lote.hectareas_calculadas === null) return true;
  return Math.abs(lote.hectareas - lote.hectareas_calculadas) > 0.005;
}

// ---------- Mapa ----------

const contenedorMapa = document.getElementById("mapa");
const mapa = hayMapa(contenedorMapa) ? crearMapaSatelital(contenedorMapa) : null;
const capaLotes = mapa ? L.featureGroup().addTo(mapa) : null;

if (mapa) {
  // Geoman en castellano, sin su barra de botones (usamos los nuestros), y sin
  // polígonos que se crucen sobre sí mismos (un "moño" no tiene un área clara).
  mapa.pm.setLang("es");
  mapa.pm.setGlobalOptions({ allowSelfIntersection: false, snappable: true, snapDistance: 15 });
}

// Mientras se dibuja, el polígono nuevo se ve blanco y verde.
const ESTILO_DIBUJO = { color: "#FFFFFF", weight: 3, fillColor: "#0F9D6E", fillOpacity: 0.35 };

function pintarMapa() {
  if (!mapa) return;
  capasPorId = dibujarLotes(capaLotes, lotes.filter((l) => !l.archivado), {
    seleccionado,
    alHacerClic: (lote) => !modo && seleccionar(lote.id, false),
  });
  leyenda.replaceChildren(armarLeyenda(lotes.filter((l) => !l.archivado)));
}

// Que se vean todos los lotes (solo la primera vez, para no mover el mapa al refrescar).
let yaEncuadrado = false;
function encuadrar() {
  if (!mapa || yaEncuadrado || capaLotes.getLayers().length === 0) return;
  const elegido = capasPorId.get(seleccionado);
  mapa.fitBounds((elegido || capaLotes).getBounds(), { padding: [24, 24], maxZoom: 17 });
  yaEncuadrado = true;
}

function seleccionar(id, irAlLote = true) {
  seleccionado = id;
  for (const lote of lotes) capasPorId.get(lote.id)?.setStyle(estiloLote(lote, lote.id === id));
  const capa = capasPorId.get(id);
  if (capa && irAlLote) mapa.fitBounds(capa.getBounds(), { padding: [40, 40], maxZoom: 17 });
  mostrarLista();
  lista.querySelector(`[data-id="${id}"]`)?.scrollIntoView({ block: "nearest" });
  // En el celular el mapa queda arriba de la lista: lo traemos a la vista.
  if (capa && irAlLote && window.matchMedia("(max-width: 900px)").matches) {
    contenedorMapa.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// ---------- Lista ----------

function mostrarLista() {
  const buscado = normalizar(buscar.value);
  const visibles = lotes.filter(
    (l) => (verArchivados.checked || !l.archivado) && (!buscado || normalizar(`${l.nombre} ${l.observaciones} ${textoCultivos(l)}`).includes(buscado)),
  );
  lista.replaceChildren();
  if (visibles.length === 0) {
    lista.append(el("li", { className: "vacio" }, lotes.length ? "Ningún lote coincide." : "Todavía no hay lotes. Tocá «Nuevo lote» y dibujalo en el mapa."));
  }
  for (const lote of visibles) lista.append(itemLote(lote));
  const activos = lotes.filter((l) => !l.archivado);
  const suma = activos.reduce((total, l) => total + (l.hectareas || 0), 0);
  totalHectareas.textContent = activos.length ? `Total: ${formatearCantidad(suma)} ha en ${activos.length} lote${activos.length === 1 ? "" : "s"}` : "";
}

function itemLote(lote) {
  const hectareas = lote.hectareas === null ? "— ha" : `${formatearCantidad(lote.hectareas)} ha`;
  const notas = [];
  if (lote.archivado) notas.push("Archivado");
  if (!lote.geometria) notas.push("Sin dibujar");
  else if (hectareasAMano(lote)) notas.push(`A mano (el dibujo da ${formatearCantidad(lote.hectareas_calculadas)} ha)`);
  if (lote.observaciones) notas.push(lote.observaciones);

  // Los cultivos de la campaña: tocar uno lo edita.
  const chips = el(
    "div",
    { className: "lote-cultivos" },
    (lote.cultivos || []).map((fila) =>
      el("button", { type: "button", className: "boton-chip", title: "Editar este cultivo", onclick: () => editarCultivo(lote, fila) }, muestraCultivo(fila.color, nombreCultivo(fila))),
    ),
    lote.archivado ? null : el("button", { type: "button", className: "boton-chip agregar", onclick: () => agregarCultivo(lote) }, "+ cultivo"),
  );

  const acciones = lote.archivado
    ? [botonIcono("archivo", "Desarchivar", { onclick: () => desarchivar(lote) })]
    : [
        botonIcono("ojo", "Ver ficha", {}, "a"),
        botonIcono("lapiz", "Editar nombre y hectáreas", { onclick: () => abrirVentanaLote(lote) }),
        lote.geometria
          ? botonIcono("mapa", "Editar la forma", { onclick: () => empezarEdicionForma(lote) })
          : botonIcono("mas", "Dibujar en el mapa", { onclick: () => empezarDibujo({ tipo: "dibujar", lote }) }),
        botonIcono("basura", "Eliminar", { className: "peligro", onclick: () => eliminar(lote) }),
      ];
  if (!lote.archivado) acciones[0].href = `lote.html?id=${lote.id}`;

  return el(
    "li",
    { className: `lote${lote.id === seleccionado ? " elegido" : ""}${lote.archivado ? " fila-archivada" : ""}`, dataset: { id: lote.id } },
    el(
      "div",
      { className: "lote-cabeza" },
      el(
        "button",
        { type: "button", className: "lote-principal", title: lote.geometria ? "Ver en el mapa" : "", onclick: () => !modo && seleccionar(lote.id) },
        el("span", { className: "fuerte" }, lote.nombre),
        el("span", { className: "lote-ha" }, hectareas),
        notas.length ? el("span", { className: "suave chico lote-detalle" }, notas.join(" · ")) : null,
      ),
      el("div", { className: "acciones-fila" }, acciones),
    ),
    campania ? chips : null,
  );
}

// ---------- Cargar datos ----------

async function cargar() {
  if (modo) return; // No refrescar mientras dibujás: se perdería lo que estás haciendo.
  try {
    [campanias, cultivos] = await Promise.all([api("GET", "/campanias"), api("GET", "/cultivos")]);
    campania = campanias.find((c) => c.id === campania?.id) || campaniaRecordada(campanias);
    llenarSelectLista(selectCampania, campanias, (c) => c.nombre, campanias.length ? "" : "Sin campañas");
    selectCampania.value = campania?.id ?? "";
    const filtro = campania ? `&campania_id=${campania.id}` : "";
    lotes = await api("GET", `/lotes?incluir_archivados=true${filtro}`);
    if (seleccionado && !lotes.some((l) => l.id === seleccionado)) seleccionado = null;
    actualizarLinkKml();
    pintarMapa();
    encuadrar();
    mostrarLista();
    const activos = lotes.filter((l) => !l.archivado).length;
    estado.textContent = textoActualizado(activos, "lote", "lotes");
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

selectCampania.addEventListener("change", () => {
  campania = campanias.find((c) => String(c.id) === selectCampania.value) || null;
  if (campania) recordarCampania(campania.id);
  cargar();
});

document.getElementById("nueva-campania").addEventListener("click", async () => {
  const nueva = await pedirCampaniaNueva(campanias);
  if (!nueva) return;
  campania = nueva;
  recordarCampania(nueva.id);
  avisar(`✅ Campaña ${nueva.nombre} creada. Ahora cargale el cultivo a cada lote.`);
  cargar();
});

// ---------- Cultivos de cada lote ----------

async function agregarCultivo(lote) {
  if (cultivos.length === 0) {
    avisar("Primero cargá los cultivos en la página Cultivos.", "error");
    return;
  }
  const guardado = await abrirVentanaCultivoLote({ lote, campanias, cultivos, campaniaId: campania?.id });
  if (!guardado) return;
  avisar(`✅ ${lote.nombre}: ${nombreCultivo(guardado)} (${guardado.campania})`);
  // Si se cargó en otra campaña, pasamos a mirar esa.
  campania = campanias.find((c) => c.id === guardado.campania_id) || campania;
  if (campania) recordarCampania(campania.id);
  cargar();
}

async function editarCultivo(lote, fila) {
  const guardado = await abrirVentanaCultivoLote({ lote, fila, campanias, cultivos });
  if (!guardado) return;
  avisar(`✅ Guardado: ${lote.nombre}, ${nombreCultivo(guardado)}`);
  cargar();
}

// ---------- Dibujar y editar ----------

function mostrarBarra(texto, conGuardar) {
  barraTexto.textContent = texto;
  barraGuardar.hidden = !conGuardar;
  barra.hidden = false;
  botonNuevo.disabled = true;
  document.body.classList.add("dibujando"); // La lista se apaga mientras tanto (ver estilos.css).
}

function terminarModo() {
  if (modo?.tipo === "forma") modo.capa.pm.disable();
  mapa?.pm.disableDraw();
  modo = null;
  barra.hidden = true;
  botonNuevo.disabled = false;
  document.body.classList.remove("dibujando");
}

function empezarDibujo(nuevoModo) {
  if (!mapa) return;
  terminarModo();
  modo = nuevoModo;
  const quien = nuevoModo.lote ? ` de «${nuevoModo.lote.nombre}»` : "";
  mostrarBarra(`Dibujá el borde${quien}: tocá cada esquina y, para cerrar, tocá el primer punto.`, false);
  mapa.pm.enableDraw("Polygon", { pathOptions: ESTILO_DIBUJO, templineStyle: { color: "#FFFFFF" }, hintlineStyle: { color: "#FFFFFF", dashArray: "5,5" } });
  contenedorMapa.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Geoman avisa con "pm:create" cuando se cerró el polígono.
mapa?.on("pm:create", async ({ layer }) => {
  const actual = modo;
  terminarModo();
  if (actual?.tipo === "dibujar") {
    // Lote que ya existía, sin forma: guardamos el dibujo y listo.
    layer.remove();
    await guardarForma(actual.lote, geometriaDe(layer));
    return;
  }
  // Lote nuevo: queda en el mapa y se piden nombre y observaciones.
  capaPendiente = layer;
  abrirVentanaLote(null, geometriaDe(layer));
});

// Si se cortó el dibujo sin cerrar el polígono (por ejemplo con Escape), salimos del modo.
mapa?.on("pm:drawend", () => {
  if (modo && modo.tipo !== "forma") terminarModo();
});

function empezarEdicionForma(lote) {
  const capa = capasPorId.get(lote.id);
  if (!capa) return;
  terminarModo();
  seleccionar(lote.id);
  modo = { tipo: "forma", lote, capa };
  const actualizar = () => mostrarBarra(`«${lote.nombre}»: arrastrá los puntos (${formatearCantidad(hectareasDe(geometriaDe(capa)))} ha).`, true);
  actualizar();
  capa.pm.enable({ allowSelfIntersection: false });
  capa.off("pm:markerdragend pm:vertexadded pm:vertexremoved");
  capa.on("pm:markerdragend pm:vertexadded pm:vertexremoved", actualizar);
}

barraGuardar.addEventListener("click", async () => {
  if (modo?.tipo !== "forma") return;
  const { lote, capa } = modo;
  terminarModo();
  await guardarForma(lote, geometriaDe(capa));
});

document.getElementById("barra-cancelar").addEventListener("click", () => {
  terminarModo();
  cargar(); // Vuelve a dibujar los lotes como estaban guardados.
});

// Guarda una forma nueva para un lote que ya existe. Si sus hectáreas eran las del
// dibujo, se recalculan; si las habías escrito a mano, se respetan.
async function guardarForma(lote, geometria) {
  try {
    const guardado = await api("PUT", `/lotes/${lote.id}`, {
      nombre: lote.nombre,
      observaciones: lote.observaciones,
      geometria,
      hectareas: hectareasAMano(lote) ? lote.hectareas : "",
    });
    const extra = hectareasAMano(guardado) ? ` (quedan las ${formatearCantidad(guardado.hectareas)} ha cargadas a mano)` : "";
    avisar(`✅ Forma guardada: ${guardado.nombre}, ${formatearCantidad(guardado.hectareas_calculadas)} ha${extra}`);
    seleccionado = guardado.id;
  } catch (error) {
    avisar(error.message, "error");
  }
  cargar();
}

// ---------- Ventana: nombre, hectáreas y observaciones ----------

// lote = null → lote nuevo (geometria = lo recién dibujado).
function abrirVentanaLote(lote, geometria = null) {
  ventanaLote = lote;
  formLote.reset();
  ventana.querySelector("h2").textContent = lote ? "Editar lote" : "Nuevo lote";
  const calculadas = lote ? lote.hectareas_calculadas : geometria ? hectareasDe(geometria) : null;
  // Si las hectáreas son las del dibujo, la ventana las propone; si no las tocás, quedan "automáticas".
  hectareasSugeridas = lote ? formatearCantidad(lote.hectareas) : formatearCantidad(calculadas);
  if (lote) completarFormulario(formLote, { nombre: lote.nombre, observaciones: lote.observaciones });
  formLote.elements.hectareas.value = hectareasSugeridas;
  ayudaHectareas.textContent =
    calculadas === null
      ? "Este lote no tiene dibujo: escribí las hectáreas o dejalas vacías."
      : `Según el dibujo: ${formatearCantidad(calculadas)} ha. Podés corregirlas; vacías = las del dibujo.`;
  abrirVentana(ventana);
}

formLote.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formLote, (datos) => {
    const automaticas = !ventanaLote || !hectareasAMano(ventanaLote);
    // Sin tocar el número propuesto → "" (que el servidor use las del dibujo).
    if (automaticas && datos.hectareas === hectareasSugeridas) datos.hectareas = "";
    if (!ventanaLote) return api("POST", "/lotes", { ...datos, geometria: geometriaDe(capaPendiente) });
    return api("PUT", `/lotes/${ventanaLote.id}`, { ...datos, geometria: ventanaLote.geometria });
  });
  if (!guardado) return;
  const eraNuevo = !ventanaLote;
  ventana.close();
  avisar(`✅ Guardado: ${guardado.nombre}${eraNuevo ? ". Tocá «+ cultivo» para cargarle qué tiene sembrado." : ""}`);
  seleccionado = guardado.id;
  cargar();
});

// Si se cierra la ventana de un lote nuevo sin guardar, se borra lo dibujado.
ventana.addEventListener("close", () => {
  capaPendiente?.remove();
  capaPendiente = null;
});

// ---------- Eliminar / archivar ----------

async function eliminar(lote) {
  if (!confirmar(`¿Eliminar el lote ${lote.nombre}? No se puede deshacer.`)) return;
  try {
    await api("DELETE", `/lotes/${lote.id}`);
    avisar(`Eliminado: ${lote.nombre}`);
  } catch (error) {
    // Con cultivos cargados no se borra (se perdería el historial): se ofrece archivarlo.
    if (error.estado === 409 && confirmar(`${lote.nombre} tiene cultivos cargados, así que no se puede eliminar. ¿Archivarlo? (deja de verse, pero se guarda su historial)`)) {
      try {
        await api("POST", `/lotes/${lote.id}/archivar`);
        avisar(`Archivado: ${lote.nombre}`);
      } catch (otroError) {
        avisar(otroError.message, "error");
      }
    } else if (error.estado !== 409) {
      avisar(error.message, "error");
    }
  }
  cargar();
}

async function desarchivar(lote) {
  try {
    await api("POST", `/lotes/${lote.id}/desarchivar`);
    avisar(`✅ ${lote.nombre} vuelve a estar activo.`);
  } catch (error) {
    avisar(error.message, "error");
  }
  cargar();
}

// ---------- Importar (KMZ, KML, GeoJSON) y exportar KML ----------
// 1) Elegís el archivo → el servidor lo lee y devuelve una vista previa (no guarda nada).
// 2) En la ventana elegís cuáles importar (y les podés cambiar el nombre) → se guardan.

const archivoImportar = document.getElementById("archivo-importar");
const ventanaImportar = document.getElementById("ventana-importar");
const formImportar = document.getElementById("form-importar");
const tablaImportar = document.getElementById("tabla-importar");
const todosImportar = document.getElementById("importar-todos");
const capaVistaPrevia = mapa ? L.featureGroup().addTo(mapa) : null;
const ESTILO_VISTA_PREVIA = { color: "#38BDF8", weight: 3, dashArray: "6 4", fillColor: "#38BDF8", fillOpacity: 0.2 };
let filasImportar = []; // [{lote (lo leído), casilla, nombre (input), estado (celda)}]

document.getElementById("boton-importar").addEventListener("click", () => archivoImportar.click());

// El archivo se manda como texto "base64" (letras y números que representan los bytes).
function leerComoBase64(archivo) {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onload = () => resolver(String(lector.result).split(",", 2)[1] || "");
    lector.onerror = () => rechazar(new Error("No se pudo leer el archivo."));
    lector.readAsDataURL(archivo); // "data:...;base64,XXXX" → nos quedamos con XXXX
  });
}

archivoImportar.addEventListener("change", async () => {
  const archivo = archivoImportar.files[0];
  archivoImportar.value = ""; // Así se puede volver a elegir el mismo archivo.
  if (!archivo) return;
  if (archivo.size > 15 * 1024 * 1024) {
    avisar("El archivo es muy grande (máximo 15 MB).", "error");
    return;
  }
  try {
    const previa = await api("POST", "/lotes/importar/leer", {
      nombre_archivo: archivo.name,
      contenido_base64: await leerComoBase64(archivo),
    });
    mostrarVistaPrevia(archivo.name, previa);
  } catch (error) {
    avisar(error.message, "error");
  }
});

// ¿Qué va a pasar con esta fila? Se recalcula si le cambiás el nombre o la tildás.
function actualizarEstadoImportar(fila) {
  const nombre = normalizar(fila.nombre.value.trim());
  const existente = lotes.find((l) => normalizar(l.nombre) === nombre);
  let texto = "Se crea";
  let color = "verde";
  if (!fila.casilla.checked) [texto, color] = ["No se importa", "gris"];
  else if (!nombre) [texto, color] = ["Falta el nombre", "rojo"];
  else if (existente) [texto, color] = [`Ya existe: se le cambia la forma${existente.archivado ? " (está archivado)" : ""}`, "ambar"];
  fila.estado.replaceChildren(pill(texto, color));
}

function mostrarVistaPrevia(nombreArchivo, previa) {
  filasImportar = [];
  tablaImportar.replaceChildren();
  capaVistaPrevia?.clearLayers();
  for (const lote of previa.lotes) {
    // Si ya hay uno con ese nombre, arranca SIN tildar: cambiar una forma tiene que ser a propósito.
    const casilla = el("input", { type: "checkbox", checked: !lote.existente, "aria-label": `Importar ${lote.nombre}` });
    const nombre = el("input", { value: lote.nombre, maxLength: 80, "aria-label": "Nombre del lote" });
    const estado = el("td", {});
    const fila = { lote, casilla, nombre, estado };
    casilla.addEventListener("change", () => {
      actualizarEstadoImportar(fila);
      todosImportar.checked = filasImportar.every((f) => f.casilla.checked);
    });
    nombre.addEventListener("input", () => actualizarEstadoImportar(fila));
    tablaImportar.append(el("tr", {}, el("td", {}, casilla), el("td", {}, nombre), el("td", { className: "numero" }, formatearCantidad(lote.hectareas)), estado));
    actualizarEstadoImportar(fila);
    filasImportar.push(fila);
    if (capaVistaPrevia) {
      L.geoJSON(lote.geometria, { style: ESTILO_VISTA_PREVIA })
        .bindTooltip(el("span", {}, el("strong", {}, lote.nombre)), { className: "etiqueta-lote" })
        .addTo(capaVistaPrevia);
    }
  }
  if (previa.lotes.length === 0) tablaImportar.append(filaVacia(4, "El archivo no tiene lotes que se puedan usar."));
  todosImportar.checked = filasImportar.length > 0 && filasImportar.every((f) => f.casilla.checked);

  const total = previa.lotes.reduce((suma, l) => suma + l.hectareas, 0);
  document.getElementById("importar-resumen").textContent =
    `${nombreArchivo}: ${previa.lotes.length} lote(s), ${formatearCantidad(total)} ha. En el mapa se ven en celeste. ` +
    "Tildá los que quieras traer; podés cambiarles el nombre.";
  const errores = document.getElementById("importar-errores");
  errores.hidden = previa.errores.length === 0;
  errores.textContent = previa.errores.length ? `⚠️ No se pueden usar: ${previa.errores.join(" · ")}` : "";

  if (capaVistaPrevia?.getLayers().length) mapa.fitBounds(capaVistaPrevia.getBounds(), { padding: [24, 24], maxZoom: 16 });
  abrirVentana(ventanaImportar);
}

todosImportar.addEventListener("change", () => {
  for (const fila of filasImportar) {
    fila.casilla.checked = todosImportar.checked;
    actualizarEstadoImportar(fila);
  }
});

formImportar.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const elegidos = filasImportar.filter((f) => f.casilla.checked);
  if (elegidos.length === 0) {
    mostrarMensaje(document.getElementById("importar-mensaje"), "Tildá al menos un lote.", "error");
    return;
  }
  const resultado = await enviarFormulario(formImportar, () =>
    api("POST", "/lotes/importar", {
      lotes: elegidos.map((f) => ({ nombre: f.nombre.value.trim(), geometria: f.lote.geometria, actualizar: true })),
    }),
  );
  if (!resultado) return;
  ventanaImportar.close();
  const partes = [];
  if (resultado.creados.length) partes.push(`${resultado.creados.length} creado(s)`);
  if (resultado.actualizados.length) partes.push(`${resultado.actualizados.length} con forma nueva`);
  if (resultado.errores.length) partes.push(`${resultado.errores.length} con error: ${resultado.errores.join(" · ")}`);
  avisar(`✅ Importación lista: ${partes.join(", ") || "nada para importar"}.`, resultado.errores.length ? "error" : "ok");
  yaEncuadrado = false; // Que el mapa muestre todos, incluidos los nuevos.
  cargar();
});

// Al cerrar la ventana (importando o no), se borra la vista previa del mapa.
ventanaImportar.addEventListener("close", () => capaVistaPrevia?.clearLayers());

// Exportar: el link pide el KML de la campaña que estás mirando (colores de sus cultivos).
const botonKml = document.getElementById("boton-kml");
function actualizarLinkKml() {
  botonKml.href = `/exportar/lotes-kml${campania ? `?campania_id=${campania.id}` : ""}`;
}

// ---------- Arranque ----------

botonNuevo.addEventListener("click", () => empezarDibujo({ tipo: "nuevo" }));
botonNuevo.before(
  botonExportar(() =>
    exportarExcel(
      "lotes",
      `Lotes ${campania?.nombre ?? ""}`.trim(),
      ["Lote", "Hectáreas", "Hectáreas del dibujo", `Cultivos ${campania?.nombre ?? ""}`.trim(), "Archivado", "Observaciones"],
      lotes.map((l) => [l.nombre, l.hectareas, l.hectareas_calculadas, textoCultivos(l), l.archivado ? "Sí" : "No", l.observaciones]),
    ),
  ),
);
buscar.addEventListener("input", mostrarLista);
verArchivados.addEventListener("change", mostrarLista);

cargar();
refrescarAutomaticamente(cargar);
