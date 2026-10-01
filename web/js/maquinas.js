// =========================================================
// maquinas.js — listado de maquinaria con filtros.
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");
const formMaquina = document.getElementById("form-maquina");

let opciones = null;
let todas = [];
let ultimasVisibles = [];

function mostrarAlertas(vencimientos) {
  const contenedor = document.getElementById("alertas");
  contenedor.replaceChildren();
  if (vencimientos.length === 0) return;
  const hayVencidos = vencimientos.some((v) => v.dias < 0);
  const alerta = el("div", { className: `alerta${hayVencidos ? " urgente" : ""}`, role: "status" });
  alerta.innerHTML = icono("calendario");
  alerta.append(
    el(
      "div",
      {},
      el("a", { href: "vencimientos.html", style: "color:inherit" }, `${vencimientos.length} vencimiento(s) en los próximos ${opciones.dias_alerta} días:`),
      el(
        "ul",
        {},
        vencimientos.map((v) =>
          el("li", {}, `${v.descripcion}${v.maquina_nombre ? ` (${v.maquina_nombre})` : ""}: ${v.dias < 0 ? "venció" : "vence"} ${describirDias(v.dias)}`),
        ),
      ),
    ),
  );
  contenedor.append(alerta);
}

function pasaFiltros(maquina, filtros) {
  if (!filtros.archivadas && maquina.archivado) return false;
  if (filtros.tipo && maquina.tipo !== filtros.tipo) return false;
  if (filtros.texto) {
    const donde = normalizar(`${maquina.nombre} ${maquina.marca} ${maquina.modelo} ${maquina.patente} ${maquina.numero_serie} ${maquina.serie_monitor}`);
    if (!donde.includes(normalizar(filtros.texto))) return false;
  }
  return true;
}

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const visibles = todas.filter((m) => pasaFiltros(m, filtros));
  ultimasVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) {
    cuerpoTabla.append(filaVacia(7, todas.length ? "Ninguna máquina coincide con los filtros." : 'Todavía no hay máquinas. Cargá la primera con "Nueva máquina".'));
  }

  for (const m of visibles) {
    const detalle = [m.marca, m.modelo, m.anio, m.patente].filter(Boolean).join(" · ");
    const nombre = el(
      "td",
      {},
      el("a", { href: `maquina.html?id=${m.id}`, className: "fuerte", style: "color:inherit" }, m.nombre),
      m.archivado ? el("span", {}, " ", pill("Archivada", "gris")) : null,
      detalle ? el("div", { className: "suave chico" }, detalle) : null,
    );
    const horas = el("td", { className: "numero" }, `${formatearCantidad(m.horas_motor)} h`);
    if (m.horas_trilla !== null) horas.append(el("div", { className: "suave chico" }, `trilla ${formatearCantidad(m.horas_trilla)} h`));

    let service = el("span", { className: "suave" }, "Sin registrar");
    const plan = m.proximo_service; // El plan de service programado más urgente (si hay).
    if (plan) {
      const color = plan.estado === "vencido" ? "rojo" : plan.estado === "proximo" ? "ambar" : "verde";
      const faltan = plan.faltan < 0 ? `pasado ${formatearCantidad(-plan.faltan)} h` : `faltan ${formatearCantidad(plan.faltan)} h`;
      service = el("div", {}, pill(plan.nombre, color), el("div", { className: "suave chico" }, faltan));
    } else if (m.ultimo_service) {
      service = el("div", {}, formatearFecha(m.ultimo_service));
      if (m.horas_ultimo_service !== null) {
        const desde = m.horas_motor - m.horas_ultimo_service;
        service.append(el("div", { className: "suave chico" }, `hace ${formatearCantidad(desde)} h de uso`));
      }
    }

    let vencimiento = el("span", { className: "suave" }, "—");
    if (m.proximo_vencimiento) {
      const dias = diasHasta(m.proximo_vencimiento);
      const color = dias < 0 ? "rojo" : dias <= opciones.dias_alerta ? "ambar" : "azul";
      vencimiento = el("div", {}, pill(formatearFecha(m.proximo_vencimiento), color), el("div", { className: "suave chico" }, describirDias(dias)));
    }

    cuerpoTabla.append(
      el(
        "tr",
        { className: m.archivado ? "fila-archivada" : "" },
        nombre,
        el("td", {}, pillDeOpcion(opciones.tipos_maquina, m.tipo)),
        horas,
        el("td", {}, service),
        el("td", { className: "numero" }, m.hectareas_totales ? `${formatearCantidad(m.hectareas_totales)} ha` : "—"),
        el("td", {}, vencimiento),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("ojo", "Ver ficha", { href: `maquina.html?id=${m.id}` }, "a"),
            botonIcono("lapiz", "Editar", { onclick: () => editar(m) }),
          ),
        ),
      ),
    );
  }
  const total = todas.filter((m) => filtros.archivadas || !m.archivado).length;
  estado.textContent = textoActualizado(total, "máquina", "máquinas") + (visibles.length !== total ? ` (mostrando ${visibles.length})` : "");
}

async function cargar() {
  try {
    const [maquinas, alertas] = await Promise.all([api("GET", "/maquinas?incluir_archivadas=true"), api("GET", "/alertas")]);
    todas = maquinas;
    mostrarTabla();
    mostrarAlertas(alertas.vencimientos);
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

let editandoId = null;
function editar(maquina) {
  editandoId = maquina.id;
  abrirVentanaMaquina(maquina);
}

document.getElementById("boton-nueva").addEventListener("click", () => {
  editandoId = null;
  abrirVentanaMaquina();
});

formMaquina.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardada = await guardarMaquina(editandoId);
  if (!guardada) return;
  document.getElementById("ventana-maquina").close();
  avisar(`✅ Guardada: ${guardada.nombre}`);
  cargar();
});

formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrarTabla));
document.getElementById("boton-actualizar").addEventListener("click", cargar);
document.getElementById("boton-actualizar").before(
  botonExportar(() =>
    exportarExcel(
      "maquinaria",
      "Maquinaria",
      ["Máquina", "Tipo", "Marca", "Modelo", "Año", "Patente", "Horas motor", "Horas trilla", "Último service", "Próximo service", "Faltan (h)", "Hectáreas", "Próximo vencimiento"],
      ultimasVisibles.map((m) => [
        m.nombre, opciones.tipos_maquina[m.tipo], m.marca, m.modelo, m.anio, m.patente, m.horas_motor, m.horas_trilla,
        m.ultimo_service, m.proximo_service?.nombre ?? "", m.proximo_service?.faltan ?? null, m.hectareas_totales, m.proximo_vencimiento,
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
  llenarSelect(formFiltros.querySelector("[data-tipos-maquina-filtro]"), opciones.tipos_maquina, "Todos los tipos");
  prepararFormMaquina(opciones);
  leerFiltrosDeUrl(formFiltros);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
