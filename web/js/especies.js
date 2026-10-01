// =========================================================
// especies.js — crear especies (ovino, porcino, gallina...) y sus categorías.
// =========================================================

const estado = document.getElementById("estado");
const lista = document.getElementById("lista-especies");
const formEspecie = document.getElementById("form-especie");
const ventanaEspecie = document.getElementById("ventana-especie");
const formCategoria = document.getElementById("form-categoria");
const ventanaCategoria = document.getElementById("ventana-categoria");

let opciones = null;
let especies = [];
let editandoEspecieId = null;
let editandoCategoriaId = null;

// Borra algo y, si el servidor no deja (porque tiene animales), muestra el motivo.
async function eliminar(url, pregunta) {
  if (!confirmar(pregunta)) return;
  try {
    await api("DELETE", url);
    cargar();
  } catch (error) {
    avisar(error.estado === 409 ? "Tiene animales cargados: no se puede eliminar." : error.message, "error");
  }
}

function filaCategoria(c) {
  return el(
    "tr",
    {},
    el("td", { className: "fuerte" }, c.nombre),
    el("td", {}, c.sexo ? pill(opciones.sexos_animal[c.sexo], c.sexo === "hembra" ? "violeta" : "azul") : el("span", { className: "suave" }, "—")),
    el("td", { className: "numero" }, formatearCantidad(c.cabezas)),
    el(
      "td",
      {},
      el(
        "div",
        { className: "acciones-fila" },
        botonIcono("lapiz", "Editar categoría", {
          onclick: () => {
            editandoCategoriaId = c.id;
            formCategoria.reset();
            completarFormulario(formCategoria, c);
            abrirVentana(ventanaCategoria);
          },
        }),
        botonIcono("basura", "Eliminar categoría", {
          className: "peligro",
          hidden: c.animales > 0,
          onclick: () => eliminar(`/categorias-animal/${c.id}`, `¿Eliminar la categoría ${c.nombre}?`),
        }),
      ),
    ),
  );
}

// Formulario chico, al pie de cada especie, para agregar una categoría.
function formNuevaCategoria(especie) {
  const formulario = el(
    "form",
    { className: "campos", style: "--columnas: 2fr 1fr auto; margin-top:12px" },
    el("label", { className: "campo" }, el("span", {}, "Nueva categoría"),
      el("input", { name: "nombre", required: true, maxLength: 40, autocomplete: "off", placeholder: "Ej: Oveja, Lechón, Ponedora" })),
    el("label", { className: "campo" }, el("span", {}, "Sexo"), el("select", { name: "sexo" })),
    el("button", { className: "boton boton-secundario", type: "submit" }, "Agregar"),
  );
  llenarSelect(formulario.elements.sexo, opciones.sexos_animal);
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const nueva = await enviarFormulario(formulario, (datos) => api("POST", `/especies/${especie.id}/categorias`, datos));
    if (!nueva) return;
    avisar(`✅ Categoría ${nueva.nombre} agregada a ${especie.nombre}.`);
    cargar();
  });
  return formulario;
}

function tarjetaEspecie(especie) {
  const gestacion = especie.dias_gestacion ? `${especie.dias_gestacion} días de gestación` : "sin gestación (no lleva tacto ni partos)";
  const cuerpo = el("tbody", {});
  if (especie.categorias.length === 0) cuerpo.append(filaVacia(4, "Todavía no tiene categorías: agregá la primera abajo."));
  for (const c of especie.categorias) cuerpo.append(filaCategoria(c));
  return el(
    "section",
    { className: "tarjeta" },
    el(
      "div",
      { className: "seccion-encabezado" },
      el("div", {}, el("h2", {}, especie.nombre), el("p", { className: "subtitulo" }, `${gestacion} · ${formatearCantidad(especie.cabezas)} animales activos`)),
      el(
        "div",
        { className: "acciones-fila" },
        botonIcono("lapiz", "Editar especie", {
          onclick: () => {
            editandoEspecieId = especie.id;
            formEspecie.reset();
            completarFormulario(formEspecie, especie);
            ventanaEspecie.querySelector("h2").textContent = `Editar ${especie.nombre}`;
            abrirVentana(ventanaEspecie);
          },
        }),
        botonIcono("basura", "Eliminar especie", {
          className: "peligro",
          hidden: especie.animales > 0,
          onclick: () => eliminar(`/especies/${especie.id}`, `¿Eliminar la especie ${especie.nombre} y sus categorías?`),
        }),
      ),
    ),
    el(
      "div",
      { className: "contenedor-tabla" },
      el(
        "table",
        {},
        el("thead", {}, el("tr", {}, el("th", {}, "Categoría"), el("th", {}, "Sexo"), el("th", { className: "numero" }, "Animales"), el("th", {}, el("span", { hidden: true }, "Acciones")))),
        cuerpo,
      ),
    ),
    formNuevaCategoria(especie),
  );
}

async function cargar() {
  try {
    especies = await api("GET", "/especies");
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
    return;
  }
  // No se redibuja si el usuario está escribiendo una categoría nueva (refresco automático).
  if (lista.contains(document.activeElement) && document.activeElement.value) return;
  lista.replaceChildren(...especies.map(tarjetaEspecie));
  estado.textContent = textoActualizado(especies.length, "especie", "especies");
}

document.getElementById("boton-nueva").addEventListener("click", () => {
  editandoEspecieId = null;
  formEspecie.reset();
  ventanaEspecie.querySelector("h2").textContent = "Nueva especie";
  abrirVentana(ventanaEspecie);
});

formEspecie.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardada = await enviarFormulario(formEspecie, (datos) => {
    const cuerpo = { nombre: datos.nombre, dias_gestacion: datos.dias_gestacion ? Number(datos.dias_gestacion) : null };
    return editandoEspecieId ? api("PUT", `/especies/${editandoEspecieId}`, cuerpo) : api("POST", "/especies", cuerpo);
  });
  if (!guardada) return;
  ventanaEspecie.close();
  avisar(`✅ Guardada: ${guardada.nombre}${editandoEspecieId ? "" : ". Ahora agregale sus categorías."}`);
  cargar();
});

formCategoria.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardada = await enviarFormulario(formCategoria, (datos) => api("PUT", `/categorias-animal/${editandoCategoriaId}`, datos));
  if (!guardada) return;
  ventanaCategoria.close();
  avisar(`✅ Guardada: ${guardada.nombre}`);
  cargar();
});

async function iniciar() {
  opciones = await cargarOpciones();
  llenarSelect(formCategoria.elements.sexo, opciones.sexos_animal);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
