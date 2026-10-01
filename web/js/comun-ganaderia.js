// =========================================================
// comun-ganaderia.js — lo que comparten el listado y la ficha de animales:
// las especies, el formulario de animal y el de eventos.
// =========================================================

let opcionesGanaderia = null;
let especies = []; // [{ id, nombre, dias_gestacion, categorias: [{ id, nombre, sexo }] }]
let animalesParaMadres = [];

async function cargarEspecies() {
  especies = await api("GET", "/especies");
  return especies;
}

function buscarEspecie(especieId) {
  return especies.find((e) => e.id === Number(especieId));
}

function buscarCategoria(categoriaId) {
  for (const especie of especies) {
    const categoria = especie.categorias.find((c) => c.id === Number(categoriaId));
    if (categoria) return { ...categoria, especie };
  }
  return null;
}

// {id: "Nombre"} para llenar un <select> de especies.
function diccionarioEspecies() {
  return Object.fromEntries(especies.map((e) => [e.id, e.nombre]));
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

// Al cambiar la especie: sus categorías y las madres posibles (hembras de esa especie).
function actualizarEspecieAnimal() {
  const formulario = document.getElementById("form-animal");
  const especie = buscarEspecie(formulario.elements.especie_id.value);
  const categorias = especie ? Object.fromEntries(especie.categorias.map((c) => [c.id, c.nombre])) : {};
  llenarSelect(formulario.elements.categoria_id, categorias, especie ? "Elegí…" : "Elegí primero la especie");
  const madres = animalesParaMadres
    .filter((a) => especie && a.especie_id === especie.id && a.sexo === "hembra" && !a.es_grupo)
    .sort((a, b) => a.caravana.localeCompare(b.caravana, "es", { numeric: true }));
  llenarSelect(formulario.elements.madre_id, Object.fromEntries(madres.map((a) => [a.id, a.caravana])), "Sin dato");
  actualizarCamposAnimal();
}

function actualizarCamposAnimal() {
  const formulario = document.getElementById("form-animal");
  const grupo = formulario.elements.es_grupo.checked;
  const categoria = buscarCategoria(formulario.elements.categoria_id.value);
  // Igual que en el servidor: solo una hembra suelta de una especie con gestación se preña.
  const reproductiva = Boolean(categoria && categoria.sexo === "hembra" && !grupo && categoria.especie.dias_gestacion);
  mostrarCampos(formulario.querySelectorAll("[data-solo-grupo]"), grupo);
  mostrarCampos(formulario.querySelectorAll("[data-solo-individual]"), !grupo);
  mostrarCampos(formulario.querySelectorAll("[data-solo-hembra]"), reproductiva);
  mostrarCampos(formulario.querySelectorAll("[data-solo-prenada]"), reproductiva && formulario.elements.estado_reproductivo.value === "prenada");
  formulario.querySelector("[data-texto-caravana]").textContent = grupo ? "Nombre del grupo" : "Caravana";
}

function prepararFormAnimal(opciones) {
  opcionesGanaderia = opciones;
  const formulario = document.getElementById("form-animal");
  llenarSelect(formulario.elements.especie_id, diccionarioEspecies(), "Elegí…");
  llenarSelect(formulario.elements.estado_reproductivo, opciones.estados_reproductivos);
  llenarSelect(formulario.elements.estado, opciones.estados_animal);
  formulario.elements.especie_id.addEventListener("change", actualizarEspecieAnimal);
  formulario.elements.categoria_id.addEventListener("change", actualizarCamposAnimal);
  formulario.elements.es_grupo.addEventListener("change", actualizarCamposAnimal);
  formulario.elements.estado_reproductivo.addEventListener("change", actualizarCamposAnimal);
}

// Con la lista de animales: madres posibles y rodeos ya usados (para sugerir).
function actualizarListasAnimal(animales) {
  animalesParaMadres = animales;
  const rodeos = [...new Set(animales.map((a) => a.rodeo).filter(Boolean))].sort();
  document.getElementById("lista-rodeos").replaceChildren(...rodeos.map((r) => el("option", { value: r })));
  return rodeos;
}

function abrirVentanaAnimal(animal = null, valoresIniciales = {}) {
  const ventana = document.getElementById("ventana-animal");
  const formulario = document.getElementById("form-animal");
  formulario.reset();
  ventana.querySelector("h2").textContent = animal ? `Editar ${animal.es_grupo ? "grupo" : "caravana"} ${animal.caravana}` : "Nuevo animal";
  const datos = animal || valoresIniciales;
  // Primero la especie (llena las categorías y madres), después el resto.
  formulario.elements.especie_id.value = datos.especie_id ?? (especies.length === 1 ? especies[0].id : "");
  actualizarEspecieAnimal();
  completarFormulario(formulario, { ...datos, madre_id: datos.madre_id ?? "" });
  // Si la madre no está en la lista (ej: se vendió), la agregamos para no perder el dato.
  if (animal?.madre_id && formulario.elements.madre_id.value !== String(animal.madre_id)) {
    formulario.elements.madre_id.append(el("option", { value: animal.madre_id }, animal.madre_caravana));
    formulario.elements.madre_id.value = animal.madre_id;
  }
  actualizarCamposAnimal();
  abrirVentana(ventana);
}

// Guarda el animal. Si la caravana ya existe, pregunta y, si se confirma, guarda igual.
function guardarAnimal(animalId = null) {
  const formulario = document.getElementById("form-animal");
  const enviar = (datos) => (animalId ? api("PUT", `/animales/${animalId}`, datos) : api("POST", "/animales", datos));
  return enviarFormulario(formulario, async (datos) => {
    try {
      return await enviar(datos);
    } catch (error) {
      if (!error.datos?.caravana_repetida) throw error;
      if (!confirmar(error.message)) throw new Error("No se guardó: la caravana ya existe. Cambiala o confirmá para repetirla.");
      return enviar({ ...datos, confirmar_repetida: true });
    }
  });
}

// ---------- Formulario de eventos ----------

const AYUDA_EVENTOS = {
  parto: "El parto deja a la hembra vacía. Una vaquillona pasa a ser vaca. Las crías se cargan después como animales nuevos.",
  aborto: "El aborto deja a la hembra vacía.",
  tacto: "Si da preñada y no ponés fecha, se calcula con los días de gestación de la especie desde el último servicio.",
  servicio: "Anotá el macho o la inseminación en el detalle.",
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

// "sinReproductivos": machos, grupos y especies sin gestación no tienen parto/tacto/servicio/aborto.
function prepararFormEvento(opciones, sinReproductivos = false) {
  opcionesGanaderia = opciones;
  const formulario = document.getElementById("form-evento");
  const tipos = { ...opciones.tipos_evento };
  if (sinReproductivos) for (const tipo of ["parto", "aborto", "tacto", "servicio"]) delete tipos[tipo];
  llenarSelect(formulario.elements.tipo, tipos);
  formulario.elements.tipo.onchange = () => actualizarCamposEvento(formulario);
  formulario.elements.fecha.value = hoyISO();
  actualizarCamposEvento(formulario);
}

function reiniciarFormEvento() {
  const formulario = document.getElementById("form-evento");
  const tipo = formulario.elements.tipo.value;
  const especie = formulario.elements.especie_id?.value;
  formulario.reset();
  formulario.elements.tipo.value = tipo; // Mantiene el tipo: útil para cargar varios seguidos.
  if (especie !== undefined) formulario.elements.especie_id.value = especie;
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
  if (!animal.reproductiva) return el("span", { className: "suave" }, "—");
  if (animal.estado_reproductivo === "prenada") return pill("Preñada", "verde");
  if (animal.estado_reproductivo === "vacia") return pill("Vacía", "ambar");
  return pill("Sin dato", "gris");
}

// La especie con un color fijo (según su posición), así cada especie se reconoce de un vistazo.
function pillEspecie(animal) {
  return pillDeOpcion(diccionarioEspecies(), String(animal.especie_id));
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
