// =========================================================
// animales.js — listado de animales (de todas las especies, sueltos o en grupo),
// resumen y carga rápida de eventos.
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
  // Los grupos cuentan por su cantidad de animales ("cabezas").
  const cabezas = (lista) => lista.reduce((total, a) => total + a.cantidad, 0);
  const porEspecie = especies
    .map((e) => [e.nombre, cabezas(activos.filter((a) => a.especie_id === e.id))])
    .filter(([, cantidad]) => cantidad > 0);
  document.getElementById("resumen").replaceChildren(
    dato(cabezas(activos), "Animales activos"),
    ...porEspecie.map(([nombre, cantidad]) => dato(cantidad, nombre)),
    dato(contar((a) => a.estado_reproductivo === "prenada"), "Preñadas"),
    dato(contar((a) => a.estado_reproductivo === "vacia"), "Vacías"),
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
  if (filtros.especie && a.especie_id !== Number(filtros.especie)) return false;
  if (filtros.categoria && a.categoria_id !== Number(filtros.categoria)) return false;
  if (filtros.rodeo && a.rodeo !== filtros.rodeo) return false;
  if (filtros.reproductivo === "prenada" && a.estado_reproductivo !== "prenada") return false;
  if (filtros.reproductivo === "vacia" && a.estado_reproductivo !== "vacia") return false;
  if (filtros.reproductivo === "sin_dato" && !(a.reproductiva && a.estado_reproductivo === "")) return false;
  if (filtros.reproductivo === "parto_proximo") {
    if (!a.fecha_probable_parto || diasHasta(a.fecha_probable_parto) > opciones.dias_alerta) return false;
  }
  if (filtros.texto) {
    const donde = normalizar(`${a.caravana} ${a.especie} ${a.categoria} ${a.raza} ${a.rodeo} ${a.observaciones} ${a.madre_caravana || ""}`);
    if (!donde.includes(normalizar(filtros.texto))) return false;
  }
  return true;
}

// Las categorías del filtro dependen de la especie elegida.
function actualizarFiltroCategorias() {
  const elegida = buscarEspecie(formFiltros.elements.especie.value);
  const categorias = {};
  for (const especie of elegida ? [elegida] : especies) {
    for (const c of especie.categorias) categorias[c.id] = elegida ? c.nombre : `${c.nombre} (${especie.nombre})`;
  }
  llenarSelect(formFiltros.elements.categoria, categorias, "Todas las categorías");
}

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const visibles = todos.filter((a) => pasaFiltros(a, filtros));
  ultimosVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) {
    cuerpoTabla.append(filaVacia(9, todos.length ? "Ningún animal coincide con los filtros." : 'Todavía no hay animales. Cargá el primero con "Nuevo animal".'));
  }
  for (const a of visibles) {
    const caravana = el("td", {}, el("a", { href: `animal.html?id=${a.id}`, className: "fuerte", style: "color:inherit" }, a.caravana));
    if (a.estado !== "activo") caravana.append(" ", pill(opciones.estados_animal[a.estado], "gris"));
    if (a.es_grupo) caravana.append(el("div", { className: "suave chico" }, `grupo de ${formatearCantidad(a.cantidad)}`));
    if (a.madre_caravana) caravana.append(el("div", { className: "suave chico" }, `madre ${a.madre_caravana}`));
    cuerpoTabla.append(
      el(
        "tr",
        { className: a.estado !== "activo" ? "fila-archivada" : "" },
        caravana,
        el("td", {}, pillEspecie(a)),
        el("td", {}, a.categoria),
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
    const [animales, alertas] = await Promise.all([api("GET", "/animales?incluir_bajas=true"), api("GET", "/alertas"), cargarEspecies()]);
    todos = animales.sort((a, b) => a.caravana.localeCompare(b.caravana, "es", { numeric: true }));
    const activos = todos.filter((a) => a.estado === "activo");
    const rodeos = actualizarListasAnimal(activos);
    llenarSelect(formFiltros.querySelector("[data-rodeos-filtro]"), Object.fromEntries(rodeos.map((r) => [r, r])), "Todos los rodeos");
    document.getElementById("lista-caravanas").replaceChildren(
      ...activos.map((a) => el("option", { value: a.caravana }, `${a.especie} · ${a.categoria}`)),
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
    // La caravana se puede repetir entre animales: si hay varios, se elige la especie.
    const encontrados = todos.filter(
      (a) =>
        a.estado === "activo" &&
        normalizar(a.caravana) === normalizar(datos.caravana) &&
        (!datos.especie_id || a.especie_id === Number(datos.especie_id)),
    );
    if (encontrados.length === 0) throw new Error(`No hay un animal activo con la caravana "${datos.caravana}".`);
    if (encontrados.length > 1) {
      const lista = encontrados.map((a) => a.especie).join(", ");
      throw new Error(`Hay ${encontrados.length} animales con la caravana "${datos.caravana}" (${lista}): elegí la especie.`);
    }
    return api("POST", `/animales/${encontrados[0].id}/eventos`, datos);
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
  avisar(`✅ Guardado: ${guardado.es_grupo ? "grupo" : "caravana"} ${guardado.caravana}`);
  cargar();
});

formFiltros.elements.especie.addEventListener("change", actualizarFiltroCategorias);
formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () =>
  setTimeout(() => {
    actualizarFiltroCategorias();
    mostrarTabla();
  }),
);
document.getElementById("boton-actualizar").addEventListener("click", cargar);
document.getElementById("boton-actualizar").before(
  botonExportar(() =>
    exportarExcel(
      "animales",
      "Animales",
      ["Caravana / grupo", "Especie", "Categoría", "Cabezas", "Raza", "Rodeo", "Nacimiento", "Estado reproductivo", "Parto probable", "Partos", "Madre", "Situación", "Observaciones"],
      ultimosVisibles.map((a) => [
        a.caravana, a.especie, a.categoria, a.cantidad, a.raza, a.rodeo, a.fecha_nacimiento,
        a.reproductiva ? opciones.estados_reproductivos[a.estado_reproductivo] : "",
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
  try {
    await cargarEspecies();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  prepararFormAnimal(opciones);
  prepararFormEvento(opciones);
  llenarSelect(formEvento.elements.especie_id, diccionarioEspecies(), "Cualquiera");
  llenarSelect(formFiltros.elements.especie, diccionarioEspecies(), "Todas las especies");
  leerFiltrosDeUrl(formFiltros);
  actualizarFiltroCategorias();
  await cargar();
  leerFiltrosDeUrl(formFiltros);
  mostrarTabla();
  refrescarAutomaticamente(cargar);
}

iniciar();
