// =========================================================
// comun-maquinaria.js — lo que comparten las páginas de maquinaria
// (listado, ficha y vencimientos).
// =========================================================

// ---------- Formulario de máquina (crear / editar) ----------

// Muestra "Horas de trilla" solo si el tipo es cosechadora.
function actualizarCamposCosechadora(formulario, tipo) {
  for (const campo of formulario.querySelectorAll("[data-solo-cosechadora]")) {
    campo.hidden = tipo !== "cosechadora";
  }
}

function prepararFormMaquina(opciones) {
  const formulario = document.getElementById("form-maquina");
  llenarSelect(formulario.elements.tipo, opciones.tipos_maquina, "Elegí…");
  formulario.elements.tipo.addEventListener("change", () =>
    actualizarCamposCosechadora(formulario, formulario.elements.tipo.value),
  );
  actualizarCamposCosechadora(formulario, "");
}

// Abre la ventana: vacía para una máquina nueva, o con sus datos para editar.
function abrirVentanaMaquina(maquina = null) {
  const ventana = document.getElementById("ventana-maquina");
  const formulario = document.getElementById("form-maquina");
  formulario.reset();
  ventana.querySelector("h2").textContent = maquina ? `Editar ${maquina.nombre}` : "Nueva máquina";
  if (maquina) completarFormulario(formulario, maquina);
  actualizarCamposCosechadora(formulario, formulario.elements.tipo.value);
  abrirVentana(ventana);
}

// Guarda (POST si es nueva, PUT si se edita). Devuelve la máquina guardada o undefined.
function guardarMaquina(maquinaId = null) {
  const formulario = document.getElementById("form-maquina");
  return enviarFormulario(formulario, (datos) =>
    maquinaId ? api("PUT", `/maquinas/${maquinaId}`, datos) : api("POST", "/maquinas", datos),
  );
}

// ---------- Vencimientos ----------

// N° de serie del monitor de la máquina, solo en licencias y suscripciones ("" si no corresponde).
function serieMonitor(v) {
  return opciones.tipos_con_monitor.includes(v.tipo) ? v.maquina_serie_monitor || "" : "";
}

// Estado de un vencimiento: { texto, color, dias }
function estadoVencimiento(vencimiento, diasAlerta = 30) {
  if (vencimiento.resuelto) return { texto: "Resuelto", color: "verde", dias: null };
  const dias = diasHasta(vencimiento.fecha_vencimiento);
  if (dias < 0) return { texto: "Vencido", color: "rojo", dias };
  if (dias <= diasAlerta) return { texto: "Vence pronto", color: "ambar", dias };
  return { texto: "Vigente", color: "azul", dias };
}

function celdaFechaVencimiento(vencimiento) {
  const estado = estadoVencimiento(vencimiento);
  return el(
    "td",
    { style: "white-space:nowrap" },
    el("div", { className: "fuerte" }, formatearFecha(vencimiento.fecha_vencimiento)),
    estado.dias !== null ? el("div", { className: "suave chico" }, describirDias(estado.dias)) : null,
  );
}

function prepararFormVencimiento(opciones, maquinas = null) {
  const formulario = document.getElementById("form-vencimiento");
  llenarSelect(formulario.elements.tipo, opciones.tipos_vencimiento, "Elegí…");
  if (maquinas && formulario.elements.maquina_id) {
    llenarSelect(formulario.elements.maquina_id, Object.fromEntries(maquinas.map((m) => [m.id, m.nombre])), "Ninguna (general)");
  }
}

function abrirVentanaVencimiento(vencimiento = null) {
  const ventana = document.getElementById("ventana-vencimiento");
  const formulario = document.getElementById("form-vencimiento");
  formulario.reset();
  ventana.querySelector("h2").textContent = vencimiento ? "Editar vencimiento" : "Nuevo vencimiento";
  formulario.querySelector("[data-solo-editar]").hidden = !vencimiento;
  if (vencimiento) completarFormulario(formulario, { ...vencimiento, maquina_id: vencimiento.maquina_id ?? "" });
  abrirVentana(ventana);
}

// Marca como resuelto (renovado): se manda el vencimiento completo con resuelto = true.
async function resolverVencimiento(vencimiento) {
  await api("PUT", `/vencimientos/${vencimiento.id}`, { ...vencimiento, resuelto: true });
  avisar(`✅ "${vencimiento.descripcion}" marcado como resuelto. Si lo renovaste, cargá el próximo vencimiento.`);
}
