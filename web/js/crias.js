// =========================================================
// crias.js — resumen de partos y crías de todas las especies.
// Las crías se cuentan desde cada parto (machos y hembras), aunque no
// se hayan cargado como animales con caravana.
// =========================================================

const estado = document.getElementById("estado");
const formFiltros = document.getElementById("filtros");

let todos = []; // partos y abortos, del más nuevo al más viejo
let ultimosVisibles = [];

function dato(valor, nombre) {
  return el("div", { className: "dato" }, el("div", { className: "dato-valor" }, valor), el("div", { className: "dato-nombre" }, nombre));
}

// Suma una lista de partos/abortos: { partos, crias, machos, hembras, multiples, abortos }
function sumar(eventos) {
  const partos = eventos.filter((e) => e.tipo === "parto");
  const machos = partos.reduce((total, e) => total + e.crias_machos, 0);
  const hembras = partos.reduce((total, e) => total + e.crias_hembras, 0);
  return {
    partos: partos.length,
    crias: machos + hembras,
    machos,
    hembras,
    multiples: partos.filter((e) => e.crias_machos + e.crias_hembras > 1).length,
    abortos: eventos.length - partos.length,
  };
}

function describirCrias(e) {
  if (e.tipo === "aborto") return el("span", { className: "suave" }, "—");
  const partes = [];
  if (e.crias_machos) partes.push(`${e.crias_machos} macho${e.crias_machos > 1 ? "s" : ""}`);
  if (e.crias_hembras) partes.push(`${e.crias_hembras} hembra${e.crias_hembras > 1 ? "s" : ""}`);
  return partes.join(" y ");
}

function pasaFiltros(e, filtros) {
  if (filtros.especie && e.especie_id !== Number(filtros.especie)) return false;
  if (filtros.tipo && e.tipo !== filtros.tipo) return false;
  if (filtros.desde && e.fecha < filtros.desde) return false;
  if (filtros.hasta && e.fecha > filtros.hasta) return false;
  if (filtros.texto) {
    const donde = normalizar(`${e.madre_caravana} ${e.rodeo} ${e.detalle} ${e.especie}`);
    if (!donde.includes(normalizar(filtros.texto))) return false;
  }
  return true;
}

function mostrar() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const visibles = todos.filter((e) => pasaFiltros(e, filtros));
  ultimosVisibles = visibles;

  // Resumen general
  const total = sumar(visibles);
  document.getElementById("resumen").replaceChildren(
    dato(total.partos, "Partos"),
    dato(total.crias, "Crías nacidas"),
    dato(total.machos, "Machos"),
    dato(total.hembras, "Hembras"),
    dato(total.multiples, "Mellizos o más"),
    dato(total.abortos, "Abortos"),
  );

  // Por especie
  const porEspecie = new Map();
  for (const e of visibles) {
    if (!porEspecie.has(e.especie)) porEspecie.set(e.especie, []);
    porEspecie.get(e.especie).push(e);
  }
  const cuerpoEspecies = document.getElementById("tabla-especies");
  cuerpoEspecies.replaceChildren();
  if (porEspecie.size === 0) cuerpoEspecies.append(filaVacia(8, "Sin datos para estos filtros."));
  for (const [especie, eventos] of [...porEspecie].sort((a, b) => a[0].localeCompare(b[0], "es"))) {
    const s = sumar(eventos);
    const numero = (valor) => el("td", { className: "numero" }, valor);
    cuerpoEspecies.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, especie),
        numero(s.partos), numero(s.crias), numero(s.machos), numero(s.hembras), numero(s.multiples), numero(s.abortos),
        numero(s.partos ? formatearCantidad(Math.round((s.crias / s.partos) * 100) / 100) : "—"),
      ),
    );
  }

  // Lista de partos y abortos
  const cuerpo = document.getElementById("tabla-partos");
  cuerpo.replaceChildren();
  if (visibles.length === 0) {
    cuerpo.append(filaVacia(7, todos.length ? "Ningún parto o aborto coincide con los filtros." : "Todavía no hay partos ni abortos registrados."));
  }
  for (const e of visibles) {
    const madre = el("td", {}, el("a", { href: `animal.html?id=${e.madre_id}`, className: "fuerte", style: "color:inherit" }, e.madre_caravana));
    if (e.madre_estado !== "activo") madre.append(" ", pill(e.madre_estado, "gris"));
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { style: "white-space:nowrap" }, formatearFecha(e.fecha)),
        madre,
        el("td", {}, e.especie),
        el("td", {}, e.tipo === "parto" ? pill("Parto", "verde") : pill("Aborto", "rojo")),
        el("td", {}, describirCrias(e)),
        el("td", { className: "numero" }, e.tipo === "parto" ? e.crias_con_caravana : "—"),
        el("td", { className: "suave chico" }, e.detalle),
      ),
    );
  }
  estado.textContent =
    textoActualizado(todos.length, "registro", "registros") + (visibles.length !== todos.length ? ` (mostrando ${visibles.length})` : "");
}

async function cargar() {
  try {
    todos = await api("GET", "/nacimientos");
    mostrar();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

document.getElementById("acciones").append(
  botonExportar(() =>
    exportarExcel(
      "crias",
      "Crías",
      ["Fecha", "Madre", "Especie", "Evento", "Crías machos", "Crías hembras", "Total crías", "Con caravana", "Detalle"],
      ultimosVisibles.map((e) => [
        e.fecha, e.madre_caravana, e.especie, e.tipo === "parto" ? "Parto" : "Aborto",
        e.crias_machos, e.crias_hembras, e.crias_machos + e.crias_hembras,
        e.tipo === "parto" ? e.crias_con_caravana : "", e.detalle,
      ]),
    ),
  ),
);

formFiltros.addEventListener("input", mostrar);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrar));

async function iniciar() {
  try {
    const especies = await api("GET", "/especies");
    llenarSelect(formFiltros.elements.especie, Object.fromEntries(especies.map((e) => [e.id, e.nombre])), "Todas las especies");
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  leerFiltrosDeUrl(formFiltros);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
