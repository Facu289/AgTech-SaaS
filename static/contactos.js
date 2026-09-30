// =========================================================
// contactos.js — proveedores, mecánicos, veterinarios...
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");
const formContacto = document.getElementById("form-contacto");
const ventana = document.getElementById("ventana-contacto");

let opciones = null;
let todos = [];
let editandoId = null;
let ultimosVisibles = [];

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const buscado = normalizar(filtros.texto);
  const visibles = todos.filter(
    (c) =>
      (!filtros.rubro || c.rubro === filtros.rubro) &&
      (!buscado || normalizar(`${c.nombre} ${c.empresa} ${c.telefono} ${c.email} ${c.notas}`).includes(buscado)),
  );
  ultimosVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) cuerpoTabla.append(filaVacia(7, todos.length ? "Ningún contacto coincide." : "Todavía no hay contactos."));
  for (const c of visibles) {
    // "tel:" abre el marcador del celular; "mailto:" abre el correo.
    const telefono = c.telefono ? el("a", { href: `tel:${c.telefono.replace(/[^\d+]/g, "")}` }, c.telefono) : "—";
    const email = c.email ? el("a", { href: `mailto:${c.email}` }, c.email) : "—";
    cuerpoTabla.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, c.nombre),
        el("td", {}, pillDeOpcion(opciones.rubros_contacto, c.rubro)),
        el("td", {}, c.empresa || "—"),
        el("td", { style: "white-space:nowrap" }, telefono),
        el("td", {}, email),
        el("td", { className: "suave chico" }, c.notas),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("lapiz", "Editar", {
              onclick: () => {
                editandoId = c.id;
                formContacto.reset();
                completarFormulario(formContacto, c);
                ventana.querySelector("h2").textContent = "Editar contacto";
                abrirVentana(ventana);
              },
            }),
            botonIcono("basura", "Eliminar", {
              className: "peligro",
              onclick: async () => {
                if (!confirmar(`¿Eliminar a ${c.nombre}?`)) return;
                await api("DELETE", `/contactos/${c.id}`);
                cargar();
              },
            }),
          ),
        ),
      ),
    );
  }
  estado.textContent = textoActualizado(todos.length, "contacto", "contactos");
}

async function cargar() {
  try {
    todos = await api("GET", "/contactos");
    mostrarTabla();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

document.getElementById("boton-nuevo").before(
  botonExportar(() =>
    exportarExcel(
      "contactos",
      "Contactos",
      ["Nombre", "Rubro", "Empresa", "Teléfono", "Email", "Notas"],
      ultimosVisibles.map((c) => [c.nombre, opciones.rubros_contacto[c.rubro], c.empresa, c.telefono, c.email, c.notas]),
    ),
  ),
);

document.getElementById("boton-nuevo").addEventListener("click", () => {
  editandoId = null;
  formContacto.reset();
  ventana.querySelector("h2").textContent = "Nuevo contacto";
  abrirVentana(ventana);
});

formContacto.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formContacto, (datos) =>
    editandoId ? api("PUT", `/contactos/${editandoId}`, datos) : api("POST", "/contactos", datos),
  );
  if (!guardado) return;
  ventana.close();
  avisar(`✅ Guardado: ${guardado.nombre}`);
  cargar();
});

formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrarTabla));

async function iniciar() {
  opciones = await cargarOpciones();
  llenarSelect(formFiltros.querySelector("[data-rubros-filtro]"), opciones.rubros_contacto, "Todos los rubros");
  llenarSelect(formContacto.elements.rubro, opciones.rubros_contacto, "Elegí…");
  leerFiltrosDeUrl(formFiltros);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
