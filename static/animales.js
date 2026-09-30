// =========================================================
// animales.js — listado de animales, resumen y carga rápida de eventos.
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");
const formEvento = document.getElementById("form-evento");
const formAnimal = document.getElementById("form-animal");

let opciones = null;
let todos = [];
let editandoId = null;
let ultimosVisibles = [];

// ---------- Resumen y alertas ----------

function mostrarResumen() {
  const activos = todos.filter((a) => a.estado === "activo");
  const contar = (condicion) => activos.filter(condicion).length;
  const dato = (valor, nombre) =>
    el("div", { className: "dato" }, el("div", { className: "dato-valor" }, valor), el("div", { className: "dato-nombre" }, nombre));
  document.getElementById("resumen").replaceChildren(
    dato(activos.length, "Animales activos"),
    dato(contar((a) => a.categoria === "vaca"), "Vacas"),
    dato(contar((a) => a.categoria === "vaquillona"), "Vaquillonas"),
    dato(contar((a) => a.estado_reproductivo === "prenada"), "Preñadas"),
    dato(contar((a) => a.estado_reproductivo === "vacia"), "Vacías"),
    dato(contar((a) => a.categoria === "ternero" || a.categoria === "ternera"), "Terneros/as"),
  );
}

function mostrarAlertas(partos) {
  const contenedor = document.getElementById("alertas");
  contenedor.replaceChildren();
  if (partos.length === 0) return;
  const atrasados = partos.some((p) => p.dias < 0);
  const alerta = el("div", { className: `alerta${atrasados ? " urgente" : ""}`, role: "status" });
  alerta.innerHTML = icono("alerta");
  alerta.append(
    el(
      "div",
      {},
      `${partos.length} parto(s) probable(s) en los próximos ${opciones.dias_alerta} días:`,
      el(
        "ul",
        {},
        partos.map((p) =>
          el("li", {}, el("a", { href: `animal.html?id=${p.id}`, style: "color:inherit" }, p.caravana), `${p.rodeo ? ` (${p.rodeo})` : ""}: ${describirDias(p.dias)} — ${formatearFecha(p.fecha_probable_parto)}`),
        ),
      ),
    ),
  );
  contenedor.append(alerta);
}

// ---------- Tabla ----------

function pasaFiltros(a, filtros) {
  if (!filtros.bajas && a.estado !== "activo") return false;
  if (filtros.categoria && a.categoria !== filtros.categoria) return false;
  if (filtros.rodeo && a.rodeo !== filtros.rodeo) return false;
  if (filtros.reproductivo === "prenada" && a.estado_reproductivo !== "prenada") return false;
  if (filtros.reproductivo === "vacia" && a.estado_reproductivo !== "vacia") return false;
  if (filtros.reproductivo === "sin_dato" && !(esHembra(a.categoria) && a.estado_reproductivo === "")) return false;
  if (filtros.reproductivo === "parto_proximo") {
    if (!a.fecha_probable_parto || diasHasta(a.fecha_probable_parto) > opciones.dias_alerta) return false;
  }
  if (filtros.texto) {
    const donde = normalizar(`${a.caravana} ${a.raza} ${a.rodeo} ${a.observaciones} ${a.madre_caravana || ""}`);
    if (!donde.includes(normalizar(filtros.texto))) return false;
  }
  return true;
}

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const visibles = todos.filter((a) => pasaFiltros(a, filtros));
  ultimosVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) {
    cuerpoTabla.append(filaVacia(8, todos.length ? "Ningún animal coincide con los filtros." : 'Todavía no hay animales. Cargá el primero con "Nuevo animal".'));
  }
  for (const a of visibles) {
    const caravana = el("td", {}, el("a", { href: `animal.html?id=${a.id}`, className: "fuerte", style: "color:inherit" }, a.caravana));
    if (a.estado !== "activo") caravana.append(" ", pill(opciones.estados_animal[a.estado], "gris"));
    if (a.madre_caravana) caravana.append(el("div", { className: "suave chico" }, `madre ${a.madre_caravana}`));
    cuerpoTabla.append(
      el(
        "tr",
        { className: a.estado !== "activo" ? "fila-archivada" : "" },
        caravana,
        el("td", {}, pillDeOpcion(opciones.categorias_animal, a.categoria)),
        el("td", {}, a.raza || el("span", { className: "suave" }, "—")),
        el("td", {}, a.rodeo || el("span", { className: "suave" }, "—")),
        el("td", {}, pillEstadoReproductivo(a)),
        el("td", {}, celdaParto(a)),
        el("td", { className: "numero" }, a.partos || "—"),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("ojo", "Ver ficha e historial", { href: `animal.html?id=${a.id}` }, "a"),
            botonIcono("lapiz", "Editar", {
              onclick: () => {
                editandoId = a.id;
                abrirVentanaAnimal(a);
              },
            }),
          ),
        ),
      ),
    );
  }
  const total = todos.filter((a) => filtros.bajas || a.estado === "activo").length;
  estado.textContent = textoActualizado(total, "animal", "animales") + (visibles.length !== total ? ` (mostrando ${visibles.length})` : "");
}

// ---------- Cargar ----------

async function cargar() {
  try {
    const [animales, alertas] = await Promise.all([api("GET", "/animales?incluir_bajas=true"), api("GET", "/alertas")]);
    todos = animales.sort((a, b) => a.caravana.localeCompare(b.caravana, "es", { numeric: true }));
    const activos = todos.filter((a) => a.estado === "activo");
    const rodeos = actualizarListasAnimal(activos);
    llenarSelect(formFiltros.querySelector("[data-rodeos-filtro]"), Object.fromEntries(rodeos.map((r) => [r, r])), "Todos los rodeos");
    document.getElementById("lista-caravanas").replaceChildren(
      ...activos.map((a) => el("option", { value: a.caravana }, opciones.categorias_animal[a.categoria])),
    );
    mostrarResumen();
    mostrarAlertas(alertas.partos);
    mostrarTabla();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

// ---------- Acciones ----------

formEvento.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const resultado = await enviarFormulario(formEvento, (datos) => {
    const animal = todos.find((a) => a.estado === "activo" && normalizar(a.caravana) === normalizar(datos.caravana));
    if (!animal) throw new Error(`No hay un animal activo con la caravana "${datos.caravana}".`);
    return api("POST", `/animales/${animal.id}/eventos`, datos);
  });
  if (!resultado) return;
  const tipo = opciones.tipos_evento[formEvento.elements.tipo.value];
  avisar(`✅ ${tipo} registrado para la caravana ${resultado.caravana}.`);
  reiniciarFormEvento();
  formEvento.elements.caravana.focus();
  cargar();
});

document.getElementById("boton-nuevo").addEventListener("click", () => {
  editandoId = null;
  abrirVentanaAnimal(null, { estado: "activo" });
});

formAnimal.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await guardarAnimal(editandoId);
  if (!guardado) return;
  document.getElementById("ventana-animal").close();
  avisar(`✅ Guardado: caravana ${guardado.caravana}`);
  cargar();
});

formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrarTabla));
document.getElementById("boton-actualizar").addEventListener("click", cargar);
document.getElementById("boton-actualizar").before(
  botonExportar(() =>
    exportarExcel(
      "animales",
      "Animales",
      ["Caravana", "Categoría", "Raza", "Rodeo", "Nacimiento", "Estado reproductivo", "Parto probable", "Partos", "Madre", "Situación", "Observaciones"],
      ultimosVisibles.map((a) => [
        a.caravana, opciones.categorias_animal[a.categoria], a.raza, a.rodeo, a.fecha_nacimiento,
        esHembra(a.categoria) ? opciones.estados_reproductivos[a.estado_reproductivo] : "",
        a.fecha_probable_parto, a.partos, a.madre_caravana || "", opciones.estados_animal[a.estado], a.observaciones,
      ]),
    ),
  ),
);

async function iniciar() {
  try {
    opciones = await cargarOpciones();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  prepararFormAnimal(opciones);
  prepararFormEvento(opciones);
  llenarSelect(formFiltros.querySelector("[data-categorias-filtro]"), opciones.categorias_animal, "Todas las categorías");
  await cargar();
  leerFiltrosDeUrl(formFiltros);
  mostrarTabla();
  refrescarAutomaticamente(cargar);
}

iniciar();
