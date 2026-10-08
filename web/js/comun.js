// =========================================================
// comun.js — lo que usan TODAS las páginas de AgroApp.
// Se carga antes que el archivo de cada página.
// =========================================================

// ---------- Íconos (SVG de trazo, como en el diseño) ----------
const ICONOS = {
  hoja: '<path d="M12 21V11"/><path d="M12 11C12 7 9 4.5 4.5 4.5 4.5 9 7.5 11 12 11Z"/><path d="M12 13c0-3.5 2.6-6 7.5-6 0 4.5-3 6-7.5 6Z"/>',
  quimico: '<path d="M9 3h6"/><path d="M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 15h9"/>',
  caja: '<path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
  tractor: '<circle cx="7" cy="17" r="3"/><circle cx="18" cy="18" r="2"/><path d="M10 17h6"/><path d="M4 14V7h7l2 4h5v5"/>',
  vaca: '<path d="M4 9c0-2 1.5-4 4-4h8c2.5 0 4 2 4 4v6a2 2 0 0 1-2 2h-1v3"/><path d="M4 9v8h3v3"/><path d="M15 5 16 3"/><path d="M17 11h.01"/>',
  flechas: '<path d="M7 4 3 8l4 4"/><path d="M3 8h13"/><path d="m17 12 4 4-4 4"/><path d="M21 16H8"/>',
  mas: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  refrescar: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 4v5h-5"/>',
  lupa: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  lapiz: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
  archivo: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8"/><path d="M10 12h4"/>',
  basura: '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>',
  historial: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>',
  alerta: '<path d="M12 3 2 21h20Z"/><path d="M12 10v5M12 18h.01"/>',
  calendario: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  persona: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  llave: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5Z"/>',
  flecha_izq: '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
  ojo: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  casa: '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
  descarga: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
  engranaje: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  plegar: '<path d="M15 6l-6 6 6 6"/>',
  desplegar: '<path d="M9 6l6 6-6 6"/>',
  lista: '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
  cerrar: '<path d="M6 6l12 12M18 6 6 18"/>',
  mapa: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z"/><path d="M9 4v14M15 6v14"/>',
  orden: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2"/><path d="M8.5 10h7M8.5 14h7M8.5 18h4"/>',
  salir: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
};

function icono(nombre, tamanio = 18) {
  return (
    `<svg width="${tamanio}" height="${tamanio}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
    `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[nombre]}</svg>`
  );
}

// ---------- Crear elementos HTML ----------
// el("td", { className: "numero" }, "12")  ->  <td class="numero">12</td>
// Los textos se ponen con textContent: nunca se ejecuta código escondido en un dato.
function el(etiqueta, propiedades = {}, ...hijos) {
  const elemento = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(propiedades)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (clave === "dataset") Object.assign(elemento.dataset, valor);
    else if (clave.startsWith("on")) elemento.addEventListener(clave.slice(2), valor);
    else if (clave in elemento) elemento[clave] = valor;
    else elemento.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    elemento.append(hijo instanceof Node ? hijo : String(hijo));
  }
  return elemento;
}

// Botón chiquito de tabla con solo un ícono. "texto" se ve al pasar el mouse.
function botonIcono(nombreIcono, texto, propiedades = {}, etiqueta = "button") {
  const clase = `boton-tabla solo-icono ${propiedades.className || ""}`.trim();
  const boton = el(etiqueta, { type: etiqueta === "button" ? "button" : null, ...propiedades, className: clase, title: texto, "aria-label": texto });
  boton.innerHTML = icono(nombreIcono, 16);
  return boton;
}

// ---------- Hablar con la API ----------

// Saca un texto entendible de una respuesta de error de FastAPI.
async function leerError(respuesta) {
  try {
    const datos = await respuesta.json();
    if (typeof datos.detail === "string") return datos.detail;
    if (Array.isArray(datos.detail)) {
      const problemas = datos.detail.map((problema) => {
        if (problema.type === "value_error") return problema.msg.replace("Value error, ", "");
        return `${problema.loc.at(-1)} (${traducirError(problema.type)})`;
      });
      return `Revisá estos datos: ${problemas.join(", ")}`;
    }
  } catch {
    // La respuesta no era JSON.
  }
  return `El servidor respondió ${respuesta.status}`;
}

function traducirError(tipo) {
  const errores = {
    missing: "falta",
    string_too_short: "vacío",
    string_too_long: "demasiado largo",
    literal_error: "opción inválida",
    greater_than: "tiene que ser mayor a 0",
    greater_than_equal: "no puede ser negativo",
    less_than_equal: "demasiado grande",
    date_from_datetime_parsing: "fecha inválida",
    int_parsing: "número inválido",
    float_parsing: "número inválido",
  };
  return errores[tipo] || "inválido";
}

// Si la sesión venció (o nunca entraste), el servidor responde 401: vamos al login.
function irAlLoginSiHaceFalta(respuesta) {
  if (respuesta.status === 401) {
    location.href = "login.html";
    throw new Error("Tenés que iniciar sesión.");
  }
}

// api("GET", "/insumos")  |  api("POST", "/insumos", { nombre: ... })
// Devuelve los datos, o lanza un Error con un mensaje entendible.
async function api(metodo, url, datos) {
  let respuesta;
  try {
    respuesta = await fetch(url, {
      method: metodo,
      headers: datos ? { "Content-Type": "application/json" } : {},
      body: datos ? JSON.stringify(datos) : undefined,
    });
  } catch {
    throw new Error("No se pudo conectar con el servidor. ¿Está corriendo el backend?");
  }
  irAlLoginSiHaceFalta(respuesta);
  if (!respuesta.ok) {
    // Además del texto, el error guarda el código y los datos que mandó el servidor
    // (ej: "caravana_repetida": así la web puede preguntar "¿guardar igual?").
    const error = new Error(await leerError(respuesta.clone()));
    error.estado = respuesta.status;
    error.datos = await respuesta.json().catch(() => ({}));
    throw error;
  }
  return respuesta.status === 204 ? null : respuesta.json();
}

// Las opciones (categorías, tipos, unidades...) se piden una sola vez.
let promesaOpciones = null;
function cargarOpciones() {
  promesaOpciones ??= api("GET", "/opciones");
  return promesaOpciones;
}

// ---------- Exportar a Excel ----------
// Manda las filas al servidor, que arma el .xlsx, y lo descarga.
// columnas: ["Insumo", "Cantidad"]   filas: [["Urea", 1500], ...]
// Los números van como números y las fechas como "AAAA-MM-DD" (Excel las entiende).
async function exportarExcel(nombre, titulo, columnas, filas) {
  try {
    const respuesta = await fetch("/exportar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, titulo, columnas, filas }),
    });
    irAlLoginSiHaceFalta(respuesta);
    if (!respuesta.ok) {
    // Además del texto, el error guarda el código y los datos que mandó el servidor
    // (ej: "caravana_repetida": así la web puede preguntar "¿guardar igual?").
    const error = new Error(await leerError(respuesta.clone()));
    error.estado = respuesta.status;
    error.datos = await respuesta.json().catch(() => ({}));
    throw error;
  }
    descargarArchivo(await respuesta.blob(), `${nombre}_${hoyISO()}.xlsx`);
    avisar(`📥 Descargado: ${filas.length} fila(s) en Excel.`);
  } catch (error) {
    avisar(error.message || "No se pudo exportar.", "error");
  }
}

// Hace que el navegador guarde un archivo (un <a download> invisible).
function descargarArchivo(blob, nombreArchivo) {
  const url = URL.createObjectURL(blob);
  const enlace = el("a", { href: url, download: nombreArchivo });
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Botón "Excel" estándar para poner en el encabezado de una lista.
function botonExportar(alHacerClic) {
  const boton = el("button", { className: "boton boton-secundario", type: "button", title: "Descargar lo que se ve (con los filtros) en Excel" });
  boton.innerHTML = icono("descarga", 16);
  boton.append("Excel");
  boton.addEventListener("click", alHacerClic);
  return boton;
}

// ---------- Formatos ----------

// Lo que escribe el usuario → número (o null si no es un número). Igual que leer_numero en Python:
// "2,5" → 2.5 | "1.500" → 1500 | "1.500,5" → 1500.5 | "0.375" → 0.375 (con 0 adelante, el punto es decimal).
function leerNumero(texto) {
  let limpio = String(texto ?? "").trim();
  if (!limpio) return null;
  if (limpio.includes(",")) limpio = limpio.replaceAll(".", "").replace(",", ".");
  else if (/^[1-9]\d{0,2}(\.\d{3})+$/.test(limpio)) limpio = limpio.replaceAll(".", "");
  const numero = Number(limpio);
  return Number.isFinite(numero) && numero >= 0 ? numero : null;
}

// Número para poner en un campo de texto: "2,084" (sin puntos de miles, para que se pueda volver a leer).
function numeroParaCampo(numero, decimales = 3) {
  if (numero === null || numero === undefined || !Number.isFinite(numero)) return "";
  return numero.toLocaleString("es-AR", { maximumFractionDigits: decimales, useGrouping: false });
}

// 1500.5 -> "1.500,5"
function formatearCantidad(numero) {
  if (numero === null || numero === undefined) return "";
  return Number(numero).toLocaleString("es-AR", { maximumFractionDigits: 2 });
}

// "2026-03-15" -> "15/03/2026"
function formatearFecha(texto) {
  if (!texto) return "";
  const [anio, mes, dia] = texto.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

// "2026-03-15 10:30:00" -> "15/03/2026 10:30"
function formatearFechaHora(texto) {
  if (!texto) return "";
  return `${formatearFecha(texto)} ${texto.slice(11, 16)}`.trim();
}

function hoyISO() {
  const hoy = new Date();
  hoy.setMinutes(hoy.getMinutes() - hoy.getTimezoneOffset()); // Fecha local, no UTC.
  return hoy.toISOString().slice(0, 10);
}

// Días desde hoy hasta la fecha (negativo si ya pasó).
function diasHasta(texto) {
  const [anio, mes, dia] = texto.slice(0, 10).split("-").map(Number);
  const fecha = new Date(anio, mes - 1, dia);
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return Math.round((fecha - hoy) / 86400000);
}

function describirDias(dias) {
  if (dias === 0) return "hoy";
  if (dias === 1) return "mañana";
  if (dias === -1) return "ayer";
  return dias > 0 ? `en ${dias} días` : `hace ${-dias} días`;
}

// Pasa a minúsculas y saca tildes, para buscar: "Agroquímico" -> "agroquimico"
function normalizar(texto) {
  return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

// ---------- Etiquetas de color ----------

const COLORES_PILL = ["", "azul", "verde", "ambar", "violeta", "rosa", "gris"];

// Cada valor de una lista recibe siempre el mismo color (según su posición).
function pill(texto, color = "") {
  return el("span", { className: `pill ${color}`.trim() }, texto);
}

function pillDeOpcion(diccionario, valor) {
  const posicion = Object.keys(diccionario).indexOf(valor);
  const color = COLORES_PILL[posicion % COLORES_PILL.length] || "";
  return pill(diccionario[valor] ?? valor, color);
}

// ---------- Formularios ----------

// Llena un <select> con un diccionario {valor: "Texto"}.
// Si "primera" tiene texto, agrega una primera opción vacía ("Todas", "Elegí…").
// Conserva lo que estaba elegido, si sigue existiendo.
function llenarSelect(select, diccionario, primera = "") {
  const elegido = select.value;
  select.replaceChildren();
  if (primera) select.append(el("option", { value: "" }, primera));
  for (const [valor, texto] of Object.entries(diccionario)) {
    select.append(el("option", { value: valor }, texto));
  }
  if ([...select.options].some((opcion) => opcion.value === elegido)) select.value = elegido;
}

// Lee todos los campos de un formulario como objeto { nombre: valor }.
// Las casillas (checkbox) se leen como true / false.
// Las casillas con data-lista (varias con el mismo nombre) se leen como una LISTA
// con los valores tildados: maquinas: ["1", "3"].
function leerFormulario(formulario) {
  const datos = Object.fromEntries(new FormData(formulario));
  for (const casilla of formulario.querySelectorAll('input[type="checkbox"]')) {
    if ("lista" in casilla.dataset) {
      datos[casilla.name] ??= [];
      if (!Array.isArray(datos[casilla.name])) datos[casilla.name] = [];
      if (casilla.checked) datos[casilla.name].push(casilla.value);
    } else {
      datos[casilla.name] = casilla.checked;
    }
  }
  for (const casilla of formulario.querySelectorAll('input[type="checkbox"][data-lista]')) {
    datos[casilla.name] ??= [];
  }
  for (const [clave, valor] of Object.entries(datos)) {
    if (typeof valor === "string") datos[clave] = valor.trim();
  }
  return datos;
}

// Pone valores en los campos de un formulario (para editar).
function completarFormulario(formulario, datos) {
  for (const campo of formulario.elements) {
    if (!campo.name || !(campo.name in datos)) continue;
    const valor = datos[campo.name];
    if (campo.type === "checkbox" && "lista" in campo.dataset) {
      campo.checked = (valor || []).map(String).includes(campo.value);
    } else if (campo.type === "checkbox") campo.checked = Boolean(valor);
    else campo.value = valor ?? "";
  }
  for (const selector of formulario.querySelectorAll("details.multi")) actualizarResumenMultiple(selector);
}

// ---------- Selector múltiple (desplegable con casillas) ----------
// En el HTML:  <details class="multi" data-nombre="maquinas" data-vacio="General (ninguna)">
//                <summary></summary><div class="multi-lista"></div></details>
// Cada opción es una casilla con data-lista, así leerFormulario devuelve una lista.

function llenarSelectorMultiple(selector, diccionario) {
  const tildados = [...selector.querySelectorAll("input:checked")].map((c) => c.value);
  const lista = selector.querySelector(".multi-lista");
  lista.replaceChildren();
  if (Object.keys(diccionario).length === 0) {
    lista.append(el("p", { className: "ayuda" }, "No hay opciones cargadas."));
  }
  // Ordenadas por nombre. (Ojo: en un objeto de JavaScript, las claves numéricas, como
  // los ids, se ordenan solas de menor a mayor; por eso ordenamos nosotros.)
  const opciones = Object.entries(diccionario).sort((a, b) => a[1].localeCompare(b[1], "es"));
  for (const [valor, texto] of opciones) {
    const casilla = el("input", { type: "checkbox", name: selector.dataset.nombre, value: valor, checked: tildados.includes(valor) });
    casilla.dataset.lista = "";
    lista.append(el("label", { className: "casilla" }, casilla, texto));
  }
  actualizarResumenMultiple(selector);
}

// El texto que se ve cerrado: "General (ninguna)", "Tractor JD", "JD, Axial" o "3 elegidas".
function actualizarResumenMultiple(selector) {
  const nombres = [...selector.querySelectorAll("input:checked")].map((c) => c.parentElement.textContent);
  let texto = selector.dataset.vacio || "Ninguna";
  if (nombres.length > 0 && nombres.length <= 2) texto = nombres.join(", ");
  if (nombres.length > 2) texto = `${nombres.length} elegidas`;
  selector.querySelector("summary").textContent = texto;
  selector.querySelector("summary").title = nombres.join(", ");
}

document.addEventListener("change", (evento) => {
  const selector = evento.target.closest("details.multi");
  if (selector) actualizarResumenMultiple(selector);
});
document.addEventListener("reset", (evento) => {
  // Después de que el navegador vacía el formulario, actualizamos los textos.
  setTimeout(() => evento.target.querySelectorAll("details.multi").forEach(actualizarResumenMultiple));
});
// Un clic afuera cierra el desplegable.
document.addEventListener("click", (evento) => {
  for (const abierto of document.querySelectorAll("details.multi[open]")) {
    if (!abierto.contains(evento.target)) abierto.open = false;
  }
});

// Envía un formulario con fetch: desactiva el botón mientras espera
// y muestra el error (si hay) en el elemento .mensaje del formulario.
// "accion" es una función async que recibe los datos y hace el pedido.
async function enviarFormulario(formulario, accion) {
  const boton = formulario.querySelector('button[type="submit"]');
  const mensaje = formulario.querySelector(".mensaje");
  if (mensaje) mensaje.hidden = true;
  boton.disabled = true;
  try {
    return await accion(leerFormulario(formulario));
  } catch (error) {
    if (mensaje) mostrarMensaje(mensaje, `⚠️ ${error.message}`, "error");
    else avisar(error.message, "error");
    return undefined;
  } finally {
    boton.disabled = false;
  }
}

function mostrarMensaje(elemento, texto, tipo) {
  elemento.textContent = texto;
  elemento.className = `mensaje ${tipo}`;
  elemento.hidden = false;
}

// Aviso flotante que desaparece solo.
let temporizadorAviso;
function avisar(texto, tipo = "ok") {
  let aviso = document.querySelector(".aviso-flotante");
  if (!aviso) {
    aviso = el("p", { role: "status" });
    document.body.append(aviso);
  }
  aviso.className = `mensaje ${tipo} aviso-flotante`;
  aviso.textContent = texto;
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => (aviso.hidden = true), tipo === "error" ? 7000 : 3500);
}

// ---------- Ventanas (dialog) ----------

// Abre un <dialog>; el botón con value="cancelar" lo cierra sin guardar.
function abrirVentana(ventana) {
  const mensaje = ventana.querySelector(".mensaje");
  if (mensaje) mensaje.hidden = true;
  ventana.showModal();
  ventana.querySelector("input:not([type=hidden]), select, textarea")?.focus();
}

document.addEventListener("click", (evento) => {
  const boton = evento.target.closest('button[value="cancelar"]');
  if (boton) {
    evento.preventDefault();
    boton.closest("dialog")?.close();
  }
});

// Pregunta antes de algo que no se puede deshacer.
function confirmar(texto) {
  return window.confirm(texto);
}

// ---------- Filtros ----------

// Guarda los filtros en la dirección (URL) de la página: así, si recargás
// o compartís el link, se mantienen. Ej: insumos?categoria=agroquimico
function guardarFiltrosEnUrl(filtros) {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== "" && valor !== false && valor !== null) parametros.set(clave, valor);
  }
  const texto = parametros.toString();
  history.replaceState(null, "", texto ? `?${texto}` : location.pathname);
}

function leerFiltrosDeUrl(formulario) {
  const parametros = new URLSearchParams(location.search);
  for (const campo of formulario.elements) {
    if (!campo.name || !parametros.has(campo.name)) continue;
    if (campo.type === "checkbox") campo.checked = parametros.get(campo.name) === "true";
    else campo.value = parametros.get(campo.name);
  }
}

// ---------- Estructura de la página ----------

// La barra lateral: grupos en el orden en que más se usan (primero el campo).
// "contador" = cuántos hay para revisar (sale de GET /alertas).
const MENU = [
  {
    titulo: "General",
    enlaces: [{ pagina: "inicio", texto: "Inicio", href: "index.html", icono: "casa" }],
  },
  {
    titulo: "Agricultura",
    enlaces: [
      { pagina: "lotes", texto: "Lotes", href: "lotes.html", icono: "mapa" },
      { pagina: "ordenes", texto: "Órdenes de trabajo", href: "ordenes.html", icono: "orden", contador: "ordenes_pendientes" },
      { pagina: "cultivos", texto: "Cultivos y campañas", href: "cultivos.html", icono: "hoja" },
    ],
  },
  {
    titulo: "Stock",
    enlaces: [
      { pagina: "quimicos", texto: "Químicos", href: "quimicos.html", icono: "quimico", contador: "stock_bajo", hoja: "quimicos" },
      { pagina: "insumos", texto: "Insumos", href: "insumos.html", icono: "caja", contador: "stock_bajo", hoja: "insumos" },
      { pagina: "repuestos", texto: "Repuestos", href: "repuestos.html", icono: "engranaje", contador: "stock_bajo", hoja: "repuestos" },
      { pagina: "movimientos", texto: "Movimientos", href: "movimientos.html", icono: "flechas" },
    ],
  },
  {
    titulo: "Maquinaria",
    enlaces: [
      { pagina: "maquinas", texto: "Máquinas", href: "maquinas.html", icono: "tractor", contador: "services" },
      { pagina: "vencimientos", texto: "Vencimientos", href: "vencimientos.html", icono: "calendario", contador: "vencimientos" },
    ],
  },
  {
    titulo: "Ganadería",
    enlaces: [
      { pagina: "animales", texto: "Animales", href: "animales.html", icono: "vaca", contador: "partos" },
      { pagina: "crias", texto: "Crías", href: "crias.html", icono: "historial" },
      { pagina: "especies", texto: "Especies", href: "especies.html", icono: "lista" },
    ],
  },
  {
    titulo: "Agenda",
    enlaces: [{ pagina: "contactos", texto: "Contactos", href: "contactos.html", icono: "persona" }],
  },
];

// Recordar si el menú quedó plegado. localStorage guarda datos en ESTE navegador;
// puede fallar (modo incógnito, permisos), por eso va dentro de try/catch.
const CLAVE_MENU = "agroapp-menu-plegado";
function leerMenuPlegado() {
  try {
    return localStorage.getItem(CLAVE_MENU) === "si";
  } catch {
    return false;
  }
}
function guardarMenuPlegado(plegado) {
  try {
    localStorage.setItem(CLAVE_MENU, plegado ? "si" : "no");
  } catch {
    // Si no se puede guardar, no pasa nada: la próxima vez arranca desplegado.
  }
}

function crearLogo() {
  const logo = el("a", { className: "logo", href: "index.html", title: "Inicio" });
  logo.innerHTML = `<span class="logo-icono">${icono("hoja", 18)}</span>`;
  logo.append(el("span", { className: "logo-texto" }, "AgroApp"));
  return logo;
}

// Arma el menú lateral (plegable) alrededor del <main> de la página.
function armarEstructura() {
  const paginaActual = document.body.dataset.pagina;
  const principal = document.querySelector("main");
  if (leerMenuPlegado()) document.body.classList.add("menu-plegado");

  const botonPlegar = el("button", { className: "boton-plegar", type: "button" });
  const actualizarBotonPlegar = () => {
    const plegado = document.body.classList.contains("menu-plegado");
    botonPlegar.innerHTML = icono(plegado ? "desplegar" : "plegar", 16);
    botonPlegar.title = plegado ? "Desplegar menú" : "Plegar menú";
    botonPlegar.setAttribute("aria-label", botonPlegar.title);
    botonPlegar.setAttribute("aria-expanded", String(!plegado));
  };
  botonPlegar.addEventListener("click", () => {
    const plegado = document.body.classList.toggle("menu-plegado");
    guardarMenuPlegado(plegado);
    actualizarBotonPlegar();
  });
  actualizarBotonPlegar();

  const nav = el("nav", { "aria-label": "Secciones" });
  for (const grupo of MENU) {
    const bloque = el("div", { className: "grupo-nav" }, el("div", { className: "titulo-nav" }, grupo.titulo));
    for (const enlace of grupo.enlaces) {
      const link = el("a", { href: enlace.href, title: enlace.texto, "aria-current": enlace.pagina === paginaActual ? "page" : null });
      link.innerHTML = icono(enlace.icono, 18);
      link.append(el("span", { className: "texto-nav" }, enlace.texto));
      if (enlace.contador) {
        const dataset = enlace.hoja ? { contador: enlace.contador, hoja: enlace.hoja } : { contador: enlace.contador };
        link.append(el("span", { className: "contador-nav", dataset, hidden: true }));
      }
      bloque.append(link);
    }
    nav.append(bloque);
  }

  const menu = el("aside", { className: "menu" }, el("div", { className: "menu-cabecera" }, crearLogo(), botonPlegar), nav, crearPieMenu());

  // Celular: barra de arriba con botón "Menú" y un fondo oscuro para cerrarlo.
  const botonMovil = el("button", { className: "boton boton-secundario", type: "button", "aria-label": "Abrir menú" });
  botonMovil.innerHTML = icono("menu", 18);
  botonMovil.append("Menú");
  const fondo = el("div", { className: "fondo-menu" });
  botonMovil.addEventListener("click", () => document.body.classList.add("menu-abierto"));
  fondo.addEventListener("click", () => document.body.classList.remove("menu-abierto"));
  const barraMovil = el("header", { className: "barra-movil" }, crearLogo(), botonMovil);

  const app = el("div", { className: "app" });
  principal.before(app);
  app.append(barraMovil, menu, fondo, principal);

  actualizarContadores();
}

// Abajo del menú: quién está usando la web y el botón "Salir".
function crearPieMenu() {
  const nombre = el("span", { className: "usuario-nombre texto-nav" });
  const usuario = el("div", { className: "usuario-menu", title: "Usuario" }, el("span", { className: "usuario-icono" }), nombre);
  usuario.firstChild.innerHTML = icono("persona", 18);
  const salir = el("button", { className: "boton-salir", type: "button", title: "Salir", "aria-label": "Salir" });
  salir.innerHTML = icono("salir", 18);
  salir.append(el("span", { className: "texto-nav" }, "Salir"));
  salir.addEventListener("click", async () => {
    try {
      await fetch("/logout", { method: "POST" });
    } finally {
      location.href = "login.html";
    }
  });
  api("GET", "/yo")
    .then((datos) => {
      nombre.textContent = datos.usuario;
      usuario.title = `Usuario: ${datos.usuario}`;
    })
    .catch(() => {});
  // "Descargar todo": un Excel con todas las tablas (antes estaba en el Inicio).
  const excel = el("a", { className: "boton-salir", href: "/exportar/completo", title: "Descargar todo (Excel, una hoja por tabla)" });
  excel.innerHTML = icono("descarga", 18);
  excel.append(el("span", { className: "texto-nav" }, "Descargar todo (Excel)"));
  return el("div", { className: "pie-menu" }, excel, usuario, salir);
}

// Muestra en la barra lateral cuántos vencimientos y partos están cerca.
async function actualizarContadores() {
  try {
    const alertas = await api("GET", "/alertas");
    for (const contador of document.querySelectorAll("[data-contador]")) {
      let lista = alertas[contador.dataset.contador];
      // Stock bajo: cada página (Insumos, Químicos, Repuestos) cuenta solo los suyos.
      if (contador.dataset.hoja) lista = lista.filter((item) => item.hoja === contador.dataset.hoja);
      const cantidad = lista.length;
      contador.textContent = cantidad;
      contador.hidden = cantidad === 0;
      contador.title = `${cantidad} para revisar`;
    }
  } catch {
    // Si falla, simplemente no se muestran los contadores.
  }
}

// ---------- Refresco automático ----------
// El bug de "cargué una salida por Telegram y la web no cambió": la página
// muestra los datos del momento en que se abrió. Ahora se vuelve a pedir
// todo cuando volvés a la pestaña y, además, cada 60 segundos.
function refrescarAutomaticamente(funcion) {
  const refrescar = () => {
    // No refrescamos mientras hay una ventana abierta (se estaría editando algo).
    if (document.hidden || document.querySelector("dialog[open]")) return;
    funcion();
    actualizarContadores();
  };
  document.addEventListener("visibilitychange", refrescar);
  setInterval(refrescar, 60000);
}

// Texto "12 insumos · actualizado 10:32:21"
function textoActualizado(cantidad, singular, plural) {
  const hora = new Date().toLocaleTimeString("es-AR");
  return `${cantidad} ${cantidad === 1 ? singular : plural} · actualizado ${hora}`;
}

// Una fila de tabla que ocupa todas las columnas, para "no hay datos".
function filaVacia(columnas, texto) {
  return el("tr", {}, el("td", { colSpan: columnas, className: "vacio" }, texto));
}

// Dibuja los íconos marcados en el HTML con data-icono="nombre".
function ponerIconos(raiz = document) {
  for (const elemento of raiz.querySelectorAll("[data-icono]")) {
    elemento.insertAdjacentHTML("afterbegin", icono(elemento.dataset.icono));
    delete elemento.dataset.icono; // Para no dibujarlo dos veces.
  }
  for (const buscador of raiz.querySelectorAll("[data-icono-lupa]")) {
    buscador.insertAdjacentHTML("afterbegin", icono("lupa"));
    delete buscador.dataset.iconoLupa;
  }
}

// Ícono de la pestaña del navegador (la hojita del logo).
function ponerFavicon() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#25C9C3"/>` +
    `<g fill="none" stroke="#06265F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(2.4 2.4) scale(0.8)">${ICONOS.hoja}</g></svg>`;
  document.head.append(el("link", { rel: "icon", href: `data:image/svg+xml,${encodeURIComponent(svg)}` }));
}

// Arma la estructura apenas carga el script (el <main> ya existe porque
// los <script> van al final del <body>).
armarEstructura();
ponerIconos();
ponerFavicon();
