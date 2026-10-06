// =========================================================
// cultivos.js — los cultivos (con su color para el mapa) y las campañas.
// =========================================================

const estado = document.getElementById("estado");
const formCultivo = document.getElementById("form-cultivo");
const ventanaCultivo = document.getElementById("ventana-cultivo");
const formCampania = document.getElementById("form-campania");
const ventanaCampania = document.getElementById("ventana-campania");

let cultivos = [];
let campanias = [];
let editandoCultivoId = null;
let editandoCampaniaId = null;

// Borra algo; si el servidor no deja (porque ya se usó en un lote), explica por qué.
async function eliminar(url, pregunta) {
  if (!confirmar(pregunta)) return;
  try {
    await api("DELETE", url);
  } catch (error) {
    avisar(error.estado === 409 ? "Ya está cargado en algún lote: no se puede eliminar." : error.message, "error");
  }
  cargar();
}

function acciones(alEditar, urlEliminar, pregunta, usado) {
  return el(
    "td",
    {},
    el(
      "div",
      { className: "acciones-fila" },
      botonIcono("lapiz", "Editar", { onclick: alEditar }),
      botonIcono("basura", "Eliminar", { className: "peligro", hidden: usado, onclick: () => eliminar(urlEliminar, pregunta) }),
    ),
  );
}

function mostrar() {
  const tablaCultivos = document.getElementById("tabla-cultivos");
  tablaCultivos.replaceChildren();
  if (cultivos.length === 0) tablaCultivos.append(filaVacia(3, "Todavía no hay cultivos."));
  for (const c of cultivos) {
    tablaCultivos.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, muestraCultivo(c.color, c.nombre)),
        el("td", { className: "numero" }, c.usos),
        acciones(
          () => {
            editandoCultivoId = c.id;
            formCultivo.reset();
            completarFormulario(formCultivo, c);
            ventanaCultivo.querySelector("h2").textContent = `Editar ${c.nombre}`;
            abrirVentana(ventanaCultivo);
          },
          `/cultivos/${c.id}`,
          `¿Eliminar el cultivo ${c.nombre}?`,
          c.usos > 0,
        ),
      ),
    );
  }

  const tablaCampanias = document.getElementById("tabla-campanias");
  tablaCampanias.replaceChildren();
  if (campanias.length === 0) tablaCampanias.append(filaVacia(3, "Todavía no hay campañas: creá la de este año."));
  for (const c of campanias) {
    tablaCampanias.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, c.nombre),
        el("td", { className: "numero" }, c.usos),
        acciones(
          () => {
            editandoCampaniaId = c.id;
            formCampania.reset();
            completarFormulario(formCampania, c);
            abrirVentana(ventanaCampania);
          },
          `/campanias/${c.id}`,
          `¿Eliminar la campaña ${c.nombre}?`,
          c.usos > 0,
        ),
      ),
    );
  }
  estado.textContent = textoActualizado(cultivos.length, "cultivo", "cultivos");
}

async function cargar() {
  try {
    [cultivos, campanias] = await Promise.all([api("GET", "/cultivos"), api("GET", "/campanias")]);
    mostrar();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

document.getElementById("boton-cultivo").addEventListener("click", () => {
  editandoCultivoId = null;
  formCultivo.reset();
  ventanaCultivo.querySelector("h2").textContent = "Nuevo cultivo";
  abrirVentana(ventanaCultivo);
});

formCultivo.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formCultivo, (datos) =>
    editandoCultivoId ? api("PUT", `/cultivos/${editandoCultivoId}`, datos) : api("POST", "/cultivos", datos),
  );
  if (!guardado) return;
  ventanaCultivo.close();
  avisar(`✅ Guardado: ${guardado.nombre}`);
  cargar();
});

document.getElementById("boton-campania").addEventListener("click", async () => {
  const nueva = await pedirCampaniaNueva(campanias);
  if (!nueva) return;
  avisar(`✅ Campaña ${nueva.nombre} creada.`);
  cargar();
});

formCampania.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardada = await enviarFormulario(formCampania, (datos) => api("PUT", `/campanias/${editandoCampaniaId}`, datos));
  if (!guardada) return;
  ventanaCampania.close();
  avisar(`✅ Guardada: ${guardada.nombre}`);
  cargar();
});

cargar();
refrescarAutomaticamente(cargar);
