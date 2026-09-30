// =========================================================
// vencimientos.js — seguros, licencias, VTV, patentes...
// =========================================================

const estado = document.getElementById("estado");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const formFiltros = document.getElementById("filtros");
const formVencimiento = document.getElementById("form-vencimiento");

let opciones = null;
let todos = [];
let editandoId = null;
let ultimosVisibles = [];

function pasaFiltros(v, filtros) {
  const info = estadoVencimiento(v, opciones.dias_alerta);
  const estadoElegido = filtros.estado || "pendientes";
  if (estadoElegido === "pendientes" && v.resuelto) return false;
  if (estadoElegido === "vencidos" && info.texto !== "Vencido") return false;
  if (estadoElegido === "proximos" && info.texto !== "Vence pronto") return false;
  if (estadoElegido === "resueltos" && !v.resuelto) return false;
  if (filtros.tipo && v.tipo !== filtros.tipo) return false;
  if (filtros.maquina === "general" && v.maquina_id !== null) return false;
  if (filtros.maquina && filtros.maquina !== "general" && String(v.maquina_id) !== filtros.maquina) return false;
  if (filtros.texto && !normalizar(`${v.descripcion} ${v.observaciones} ${v.maquina_nombre || ""}`).includes(normalizar(filtros.texto))) return false;
  return true;
}

function mostrarTabla() {
  const filtros = leerFormulario(formFiltros);
  guardarFiltrosEnUrl(filtros);
  const visibles = todos.filter((v) => pasaFiltros(v, filtros));
  ultimosVisibles = visibles;
  cuerpoTabla.replaceChildren();
  if (visibles.length === 0) cuerpoTabla.append(filaVacia(6, "No hay vencimientos con esos filtros."));

  for (const v of visibles) {
    const info = estadoVencimiento(v, opciones.dias_alerta);
    const acciones = el("div", { className: "acciones-fila" });
    if (!v.resuelto) {
      acciones.append(
        botonIcono("check", "Marcar como resuelto / renovado", {
          onclick: async () => {
            try {
              await resolverVencimiento(v);
              cargar();
            } catch (error) {
              avisar(error.message, "error");
            }
          },
        }),
      );
    }
    acciones.append(
      botonIcono("lapiz", "Editar", {
        onclick: () => {
          editandoId = v.id;
          abrirVentanaVencimiento(v);
        },
      }),
      botonIcono("basura", "Eliminar", {
        className: "peligro",
        onclick: async () => {
          if (!confirmar(`¿Eliminar "${v.descripcion}"?`)) return;
          try {
            await api("DELETE", `/vencimientos/${v.id}`);
            cargar();
          } catch (error) {
            avisar(error.message, "error");
          }
        },
      }),
    );
    cuerpoTabla.append(
      el(
        "tr",
        { className: v.resuelto ? "fila-archivada" : "" },
        celdaFechaVencimiento(v),
        el("td", {}, el("div", { className: "fuerte" }, v.descripcion), v.observaciones ? el("div", { className: "suave chico" }, v.observaciones) : null),
        el("td", {}, pillDeOpcion(opciones.tipos_vencimiento, v.tipo)),
        el("td", {}, v.maquina_id ? el("a", { href: `maquina.html?id=${v.maquina_id}` }, v.maquina_nombre) : el("span", { className: "suave" }, "General")),
        el("td", {}, pill(info.texto, info.color)),
        el("td", {}, acciones),
      ),
    );
  }
  estado.textContent = textoActualizado(visibles.length, "vencimiento", "vencimientos");
}

async function cargar() {
  try {
    const [vencimientos, maquinas] = await Promise.all([api("GET", "/vencimientos?incluir_resueltos=true"), api("GET", "/maquinas")]);
    todos = vencimientos;
    prepararFormVencimiento(opciones, maquinas);
    llenarSelect(
      formFiltros.querySelector("[data-maquinas-filtro]"),
      { general: "Generales (sin máquina)", ...Object.fromEntries(maquinas.map((m) => [m.id, m.nombre])) },
      "Todas las máquinas",
    );
    mostrarTabla();
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

document.getElementById("boton-nuevo").addEventListener("click", () => {
  editandoId = null;
  abrirVentanaVencimiento();
});

formVencimiento.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formVencimiento, (datos) =>
    editandoId ? api("PUT", `/vencimientos/${editandoId}`, datos) : api("POST", "/vencimientos", datos),
  );
  if (!guardado) return;
  document.getElementById("ventana-vencimiento").close();
  avisar("✅ Vencimiento guardado.");
  cargar();
});

formFiltros.addEventListener("input", mostrarTabla);
formFiltros.addEventListener("submit", (evento) => evento.preventDefault());
formFiltros.addEventListener("reset", () => setTimeout(mostrarTabla));
document.getElementById("boton-actualizar").addEventListener("click", cargar);
document.getElementById("boton-actualizar").before(
  botonExportar(() =>
    exportarExcel(
      "vencimientos",
      "Vencimientos",
      ["Vence", "Descripción", "Tipo", "Máquina", "Estado", "Observaciones"],
      ultimosVisibles.map((v) => [
        v.fecha_vencimiento, v.descripcion, opciones.tipos_vencimiento[v.tipo], v.maquina_nombre || "General",
        estadoVencimiento(v, opciones.dias_alerta).texto, v.observaciones,
      ]),
    ),
  ),
);

async function iniciar() {
  opciones = await cargarOpciones();
  llenarSelect(formFiltros.querySelector("[data-tipos-vencimiento-filtro]"), opciones.tipos_vencimiento, "Todos los tipos");
  await cargar();
  leerFiltrosDeUrl(formFiltros);
  mostrarTabla();
  refrescarAutomaticamente(cargar);
}

iniciar();
