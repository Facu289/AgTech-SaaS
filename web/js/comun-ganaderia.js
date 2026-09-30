// =========================================================
// comun-ganaderia.js — lo que comparten el listado y la ficha de animales:
// el formulario de animal y el de eventos.
// =========================================================

let opcionesGanaderia = null;

function esHembra(categoria) {
  return opcionesGanaderia.hembras.includes(categoria);
}

// Habilita/oculta un grupo de campos. Los campos ocultos se DESHABILITAN,
// así no se mandan al servidor (FormData ignora los campos disabled).
function mostrarCampos(contenedores, visible) {
  for (const contenedor of contenedores) {
    contenedor.hidden = !visible;
    for (const campo of contenedor.querySelectorAll("input, select, textarea")) campo.disabled = !visible;
  }
}

// ---------- Formulario de animal ----------

function actualizarCamposAnimal() {
  const formulario = document.getElementById("form-animal");
  const hembra = esHembra(formulario.elements.categoria.value);
  mostrarCampos(formulario.querySelectorAll("[data-solo-hembra]"), hembra);
  mostrarCampos(formulario.querySelectorAll("[data-solo-prenada]"), hembra && formulario.elements.estado_reproductivo.value === "prenada");
}

function prepararFormAnimal(opciones) {
  opcionesGanaderia = opciones;
  const formulario = document.getElementById("form-animal");
  llenarSelect(formulario.elements.categoria, opciones.categorias_animal, "Elegí…");
  llenarSelect(formulario.elements.estado_reproductivo, opciones.estados_reproductivos);
  llenarSelect(formulario.elements.estado, opciones.estados_animal);
  formulario.elements.categoria.addEventListener("change", actualizarCamposAnimal);
  formulario.elements.estado_reproductivo.addEventListener("change", actualizarCamposAnimal);
}

// Con la lista de animales: madres posibles y rodeos ya usados (para sugerir).
function actualizarListasAnimal(animales) {
  const formulario = document.getElementById("form-animal");
  const hembras = animales
    .filter((a) => a.categoria === "vaca" || a.categoria === "vaquillona")
    .sort((a, b) => a.caravana.localeCompare(b.caravana, "es", { numeric: true }));
  llenarSelect(formulario.elements.madre_id, Object.fromEntries(hembras.map((a) => [a.id, a.caravana])), "Sin dato");
  const rodeos = [...new Set(animales.map((a) => a.rodeo).filter(Boolean))].sort();
  document.getElementById("lista-rodeos").replaceChildren(...rodeos.map((r) => el("option", { value: r })));
  return rodeos;
}

function abrirVentanaAnimal(animal = null, valoresIniciales = {}) {
  const ventana = document.getElementById("ventana-animal");
  const formulario = document.getElementById("form-animal");
  formulario.reset();
  ventana.querySelector("h2").textContent = animal ? `Editar caravana ${animal.caravana}` : "Nuevo animal";
  const datos = animal || valoresIniciales;
  completarFormulario(formulario, { ...datos, madre_id: datos.madre_id ?? "" });
  // Si la madre no está en la lista (ej: se vendió), la agregamos para no perder el dato.
  if (animal?.madre_id && formulario.elements.madre_id.value !== String(animal.madre_id)) {
    formulario.elements.madre_id.append(el("option", { value: animal.madre_id }, animal.madre_caravana));
    formulario.elements.madre_id.value = animal.madre_id;
  }
  actualizarCamposAnimal();
  abrirVentana(ventana);
}

function guardarAnimal(animalId = null) {
  const formulario = document.getElementById("form-animal");
  return enviarFormulario(formulario, (datos) =>
    animalId ? api("PUT", `/animales/${animalId}`, datos) : api("POST", "/animales", datos),
  );
}

// ---------- Formulario de eventos ----------

const AYUDA_EVENTOS = {
  parto: "El parto deja a la hembra vacía. Una vaquillona pasa a ser vaca. Las crías se cargan después como animales nuevos.",
  aborto: "El aborto deja a la hembra vacía.",
  tacto: "Si da preñada y no ponés fecha, se calcula a 283 días del último servicio cargado.",
  servicio: "Anotá el toro o la inseminación en el detalle.",
  sanidad: "Vacunas, desparasitaciones, curaciones…",
  observacion: "Cualquier otra cosa para dejar registrada.",
};

function actualizarCamposEvento(formulario) {
  const tipo = formulario.elements.tipo.value;
  for (const grupo of ["parto", "tacto"]) {
    mostrarCampos(formulario.querySelectorAll(`[data-solo-evento="${grupo}"]`), tipo === grupo);
  }
  document.getElementById("ayuda-evento").textContent = AYUDA_EVENTOS[tipo] || "";
}

// "soloMachos": en la ficha de un macho no se ofrecen parto/tacto/servicio/aborto.
function prepararFormEvento(opciones, soloMachos = false) {
  opcionesGanaderia = opciones;
  const formulario = document.getElementById("form-evento");
  const tipos = { ...opciones.tipos_evento };
  if (soloMachos) for (const tipo of ["parto", "aborto", "tacto", "servicio"]) delete tipos[tipo];
  llenarSelect(formulario.elements.tipo, tipos);
  formulario.elements.tipo.addEventListener("change", () => actualizarCamposEvento(formulario));
  formulario.elements.fecha.value = hoyISO();
  actualizarCamposEvento(formulario);
}

function reiniciarFormEvento() {
  const formulario = document.getElementById("form-evento");
  const tipo = formulario.elements.tipo.value;
  formulario.reset();
  formulario.elements.tipo.value = tipo; // Mantiene el tipo: útil para cargar varios seguidos.
  formulario.elements.fecha.value = hoyISO();
  actualizarCamposEvento(formulario);
}

// Texto que describe un evento: "Parto: mellizos (1 macho y 1 hembra)"
function describirEvento(evento) {
  const partes = [];
  if (evento.tipo === "parto") {
    const total = evento.crias_machos + evento.crias_hembras;
    const nombre = { 1: "", 2: "mellizos: ", 3: "trillizos: " }[total] ?? `${total} crías: `;
    const detalle = [];
    if (evento.crias_machos) detalle.push(`${evento.crias_machos} macho${evento.crias_machos > 1 ? "s" : ""}`);
    if (evento.crias_hembras) detalle.push(`${evento.crias_hembras} hembra${evento.crias_hembras > 1 ? "s" : ""}`);
    partes.push(detalle.length ? nombre + detalle.join(" y ") : "sin crías registradas");
  }
  if (evento.resultado) partes.push(opcionesGanaderia.estados_reproductivos[evento.resultado]);
  if (evento.detalle) partes.push(evento.detalle);
  return partes.join(" · ");
}

// ---------- Etiquetas ----------

function pillEstadoReproductivo(animal) {
  if (!esHembra(animal.categoria)) return el("span", { className: "suave" }, "—");
  if (animal.estado_reproductivo === "prenada") return pill("Preñada", "verde");
  if (animal.estado_reproductivo === "vacia") return pill("Vacía", "ambar");
  return pill("Sin dato", "gris");
}

function celdaParto(animal) {
  if (!animal.fecha_probable_parto) return el("span", { className: "suave" }, "—");
  const dias = diasHasta(animal.fecha_probable_parto);
  const color = dias < 0 ? "rojo" : dias <= opcionesGanaderia.dias_alerta ? "ambar" : "azul";
  return el("div", {}, pill(formatearFecha(animal.fecha_probable_parto), color), el("div", { className: "suave chico" }, describirDias(dias)));
}

// Edad aproximada: "2 años y 3 meses", "5 meses", "12 días"
function edad(fechaNacimiento) {
  if (!fechaNacimiento) return "";
  const dias = -diasHasta(fechaNacimiento);
  if (dias < 60) return `${dias} días`;
  const meses = Math.floor(dias / 30.44);
  if (meses < 24) return `${meses} meses`;
  const anios = Math.floor(meses / 12);
  const resto = meses % 12;
  return `${anios} años${resto ? ` y ${resto} meses` : ""}`;
}
