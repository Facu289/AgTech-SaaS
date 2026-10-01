// =========================================================
// maquina.js — ficha de UNA máquina (maquina.html?id=3).
// =========================================================

const MAQUINA_ID = new URLSearchParams(location.search).get("id");
const titulo = document.getElementById("titulo");

let opciones = null;
let ficha = null; // { maquina, mantenimientos, trabajos, vencimientos, repuestos }

// ---------- Mostrar ----------

function dato(valor, nombre) {
  return el("div", { className: "dato" }, el("div", { className: "dato-valor" }, valor), el("div", { className: "dato-nombre" }, nombre));
}

function mostrarEncabezado(m) {
  document.title = `${m.nombre} · AgroApp`;
  titulo.replaceChildren(m.nombre, " ", pillDeOpcion(opciones.tipos_maquina, m.tipo));
  if (m.archivado) titulo.append(" ", pill("Archivada", "gris"));
  document.getElementById("subtitulo").textContent = [m.marca, m.modelo, m.anio].filter(Boolean).join(" · ");
  document.getElementById("acciones-ficha").hidden = false;
  const botonArchivar = document.getElementById("boton-archivar");
  botonArchivar.lastChild.textContent = m.archivado ? "Desarchivar" : "Archivar";

  const resumen = document.getElementById("resumen");
  resumen.replaceChildren(dato(`${formatearCantidad(m.horas_motor)} h`, "Horas motor"));
  if (m.tipo === "cosechadora") resumen.append(dato(`${formatearCantidad(m.horas_trilla ?? 0)} h`, "Horas de trilla"));
  if (m.ultimo_service) {
    const desde = m.horas_ultimo_service !== null ? ` · hace ${formatearCantidad(m.horas_motor - m.horas_ultimo_service)} h` : "";
    resumen.append(dato(formatearFecha(m.ultimo_service), `Último service${desde}`));
  } else {
    resumen.append(dato("—", "Último service"));
  }
  resumen.append(dato(`${formatearCantidad(m.hectareas_totales)} ha`, "Hectáreas trabajadas"));

  const datos = document.getElementById("datos");
  const campos = [
    ["Marca", m.marca], ["Modelo", m.modelo], ["Año", m.anio], ["N° de serie", m.numero_serie],
    ["N° de serie del monitor", m.serie_monitor],
    ["Patente", m.patente], ["Cargada el", formatearFecha(m.creado_en)], ["Observaciones", m.observaciones],
  ];
  // Cada par (nombre, valor) va en su propio <div>, así queda alineado en la grilla.
  datos.replaceChildren(...campos.map(([nombre, valor]) => el("div", {}, el("dt", {}, nombre), el("dd", {}, valor || "—"))));

  const formHoras = document.getElementById("form-horas");
  completarFormulario(formHoras, { horas_motor: m.horas_motor, horas_trilla: m.horas_trilla ?? "" });
  actualizarCamposCosechadora(formHoras, m.tipo);
  document.getElementById("link-repuestos").href = `repuestos.html?maquina=${m.id}`;
}

function botonBorrar(texto, accion) {
  return botonIcono("basura", texto, {
    className: "peligro",
    onclick: async () => {
      if (!confirmar(`¿${texto}? No se puede deshacer.`)) return;
      try {
        await accion();
        avisar("Eliminado.");
        cargar();
      } catch (error) {
        avisar(error.message, "error");
      }
    },
  });
}

// ---------- Service programado ----------

const TEXTO_ESTADO_PLAN = { ok: ["Al día", "verde"], proximo: ["Próximo", "ambar"], vencido: ["Vencido", "rojo"] };
let editandoPlanId = null;

function textoFaltan(plan) {
  return plan.faltan < 0 ? `pasado por ${formatearCantidad(-plan.faltan)} h` : `faltan ${formatearCantidad(plan.faltan)} h`;
}

function mostrarPlanes() {
  const cuerpo = document.getElementById("tabla-planes");
  cuerpo.replaceChildren();
  if (ficha.planes.length === 0) cuerpo.append(filaVacia(6, 'Sin planes. Creá uno con "Nuevo plan" (ej: aceite cada 250 h).'));
  for (const plan of ficha.planes) {
    const [texto, color] = plan.activo ? TEXTO_ESTADO_PLAN[plan.estado] : ["Inactivo", "gris"];
    const trilla = plan.medida === "trilla" ? " de trilla" : "";
    cuerpo.append(
      el(
        "tr",
        { className: plan.activo ? "" : "fila-archivada" },
        el("td", { className: "fuerte" }, plan.nombre),
        el("td", { className: "numero" }, `${formatearCantidad(plan.cada_horas)} h${trilla}`),
        el("td", {}, `${formatearCantidad(plan.ultima_horas)} h`, plan.ultima_fecha ? el("div", { className: "suave chico" }, formatearFecha(plan.ultima_fecha)) : null),
        el("td", { className: "numero" }, `${formatearCantidad(plan.proximo)} h`, el("div", { className: "suave chico", style: "font-weight:400" }, textoFaltan(plan))),
        el("td", {}, pill(texto, color)),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("check", "Marcar hecho ahora", { onclick: () => abrirMantenimiento([plan.id], `${plan.nombre}`) }),
            botonIcono("lapiz", "Editar plan", {
              onclick: () => {
                editandoPlanId = plan.id;
                const formulario = document.getElementById("form-plan");
                formulario.reset();
                completarFormulario(formulario, { ...plan, ultima_horas: plan.ultima_horas, ultima_fecha: plan.ultima_fecha ?? "" });
                document.querySelector("#ventana-plan h2").textContent = "Editar plan de service";
                abrirVentana(document.getElementById("ventana-plan"));
              },
            }),
            botonBorrar(`Eliminar el plan "${plan.nombre}"`, () => api("DELETE", `/planes/${plan.id}`)),
          ),
        ),
      ),
    );
  }
}

// Abre "Registrar service" con los planes indicados ya tildados.
function abrirMantenimiento(planesTildados = [], descripcion = "") {
  const formulario = document.getElementById("form-mantenimiento");
  formulario.reset();
  completarFormulario(formulario, { fecha: hoyISO(), horas: ficha.maquina.horas_motor, tipo: "service", descripcion });
  const activos = ficha.planes.filter((p) => p.activo);
  document.getElementById("campo-planes").hidden = activos.length === 0;
  document.getElementById("casillas-planes").replaceChildren(
    ...activos.map((p) =>
      el("label", { className: "casilla" }, el("input", { type: "checkbox", value: p.id, checked: planesTildados.includes(p.id) }), `${p.nombre} (${textoFaltan(p)})`),
    ),
  );
  abrirVentana(document.getElementById("ventana-mantenimiento"));
}

function mostrarMantenimientos() {
  const cuerpo = document.getElementById("tabla-mantenimientos");
  cuerpo.replaceChildren();
  if (ficha.mantenimientos.length === 0) cuerpo.append(filaVacia(6, "Sin services ni arreglos registrados."));
  for (const m of ficha.mantenimientos) {
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { style: "white-space:nowrap" }, formatearFecha(m.fecha)),
        el("td", {}, pill(opciones.tipos_mantenimiento[m.tipo], m.tipo === "service" ? "" : "ambar")),
        el("td", { className: "numero" }, m.horas !== null ? `${formatearCantidad(m.horas)} h` : "—"),
        el("td", {}, m.descripcion),
        el("td", { className: "numero" }, m.costo !== null ? `$ ${formatearCantidad(m.costo)}` : "—"),
        el("td", {}, el("div", { className: "acciones-fila" }, botonBorrar("Eliminar este registro", () => api("DELETE", `/mantenimientos/${m.id}`)))),
      ),
    );
  }
}

function mostrarTrabajos() {
  const cuerpo = document.getElementById("tabla-trabajos");
  const tipo = document.getElementById("filtro-trabajos").value;
  const trabajos = ficha.trabajos.filter((t) => !tipo || t.tipo === tipo);
  cuerpo.replaceChildren();
  if (trabajos.length === 0) cuerpo.append(filaVacia(7, "Sin trabajos registrados."));
  for (const t of trabajos) {
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { style: "white-space:nowrap" }, formatearFecha(t.fecha)),
        el("td", {}, pillDeOpcion(opciones.tipos_trabajo, t.tipo)),
        el("td", { className: "numero" }, `${formatearCantidad(t.hectareas)} ha`),
        el("td", {}, t.lote || "—"),
        el("td", {}, t.cultivo || "—"),
        el("td", { className: "suave" }, t.observaciones || ""),
        el("td", {}, el("div", { className: "acciones-fila" }, botonBorrar("Eliminar este trabajo", () => api("DELETE", `/trabajos/${t.id}`)))),
      ),
    );
  }
  if (trabajos.length > 1) {
    const total = trabajos.reduce((suma, t) => suma + t.hectareas, 0);
    cuerpo.append(el("tr", {}, el("td", { colSpan: 2, className: "fuerte" }, "Total"), el("td", { className: "numero" }, `${formatearCantidad(total)} ha`), el("td", { colSpan: 4 })));
  }
}

function mostrarVencimientos() {
  const cuerpo = document.getElementById("tabla-vencimientos");
  cuerpo.replaceChildren();
  if (ficha.vencimientos.length === 0) cuerpo.append(filaVacia(5, "Sin vencimientos cargados (seguro, VTV, patente…)."));
  for (const v of ficha.vencimientos) {
    const estado = estadoVencimiento(v, opciones.dias_alerta);
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
    acciones.append(botonBorrar("Eliminar este vencimiento", () => api("DELETE", `/vencimientos/${v.id}`)));
    cuerpo.append(
      el(
        "tr",
        {},
        celdaFechaVencimiento(v),
        el("td", { className: "fuerte" }, v.descripcion),
        el("td", {}, pillDeOpcion(opciones.tipos_vencimiento, v.tipo)),
        el("td", {}, pill(estado.texto, estado.color)),
        el("td", {}, acciones),
      ),
    );
  }
}

function mostrarRepuestos() {
  const cuerpo = document.getElementById("tabla-repuestos");
  cuerpo.replaceChildren();
  if (ficha.repuestos.length === 0) cuerpo.append(filaVacia(4, 'Ningún repuesto vinculado. En Repuestos, elegí esta máquina en "Para la máquina".'));
  for (const r of ficha.repuestos) {
    const tipo = opciones.subcategorias.repuesto[r.subcategoria];
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { className: "fuerte" }, r.nombre),
        el("td", {}, tipo ? pill(tipo) : "—"),
        el("td", { className: `numero${r.cantidad === 0 ? " sin-stock" : ""}` }, formatearCantidad(r.cantidad)),
        el("td", { className: "suave" }, r.unidad),
      ),
    );
  }
}

async function cargar() {
  try {
    ficha = await api("GET", `/maquinas/${MAQUINA_ID}`);
  } catch (error) {
    titulo.textContent = "No se pudo cargar la máquina";
    document.getElementById("subtitulo").textContent = error.message;
    return;
  }
  mostrarEncabezado(ficha.maquina);
  mostrarPlanes();
  mostrarMantenimientos();
  mostrarTrabajos();
  mostrarVencimientos();
  mostrarRepuestos();
}

// ---------- Formularios ----------

function alGuardar(formulario, accion, mensaje) {
  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const resultado = await enviarFormulario(formulario, accion);
    if (resultado === undefined) return;
    formulario.closest("dialog")?.close();
    avisar(mensaje);
    cargar();
  });
}

alGuardar(document.getElementById("form-horas"), (datos) => api("POST", `/maquinas/${MAQUINA_ID}/horas`, datos), "✅ Horas actualizadas.");
alGuardar(document.getElementById("form-maquina"), () => guardarMaquina(MAQUINA_ID), "✅ Datos guardados.");
alGuardar(
  document.getElementById("form-mantenimiento"),
  (datos) => {
    // Las casillas de planes no tienen "name": las leemos aparte y mandamos sus ids.
    const planes = [...document.querySelectorAll("#casillas-planes input:checked")].map((c) => Number(c.value));
    return api("POST", `/maquinas/${MAQUINA_ID}/mantenimientos`, { ...datos, planes });
  },
  "✅ Registrado.",
);
alGuardar(
  document.getElementById("form-plan"),
  (datos) => (editandoPlanId ? api("PUT", `/planes/${editandoPlanId}`, datos) : api("POST", `/maquinas/${MAQUINA_ID}/planes`, datos)),
  "✅ Plan guardado.",
);

document.getElementById("boton-plan").addEventListener("click", () => {
  editandoPlanId = null;
  const formulario = document.getElementById("form-plan");
  formulario.reset();
  formulario.elements.medida.value = "motor";
  document.querySelector("#ventana-plan h2").textContent = "Nuevo plan de service";
  abrirVentana(document.getElementById("ventana-plan"));
});
alGuardar(document.getElementById("form-trabajo"), (datos) => api("POST", `/maquinas/${MAQUINA_ID}/trabajos`, datos), "✅ Trabajo registrado.");
alGuardar(
  document.getElementById("form-vencimiento"),
  (datos) => api("POST", "/vencimientos", { ...datos, maquina_id: MAQUINA_ID }),
  "✅ Vencimiento agregado.",
);

document.getElementById("boton-editar").addEventListener("click", () => abrirVentanaMaquina(ficha.maquina));

document.getElementById("boton-mantenimiento").addEventListener("click", () => abrirMantenimiento());

document.getElementById("boton-trabajo").addEventListener("click", () => {
  const formulario = document.getElementById("form-trabajo");
  formulario.reset();
  formulario.elements.fecha.value = hoyISO();
  abrirVentana(document.getElementById("ventana-trabajo"));
});

document.getElementById("boton-vencimiento").addEventListener("click", () => abrirVentanaVencimiento());

document.getElementById("filtro-trabajos").addEventListener("change", mostrarTrabajos);

// Archivar si tiene historial; si está vacía, se puede eliminar.
document.getElementById("boton-archivar").addEventListener("click", async () => {
  const m = ficha.maquina;
  try {
    if (m.archivado) {
      await api("POST", `/maquinas/${m.id}/desarchivar`);
      avisar("Máquina desarchivada.");
      return cargar();
    }
    const vacia = !ficha.mantenimientos.length && !ficha.trabajos.length && !ficha.vencimientos.length && !ficha.repuestos.length && !ficha.planes.length;
    if (vacia && confirmar(`"${m.nombre}" no tiene historial.\n¿La eliminás definitivamente? (Cancelar = solo archivarla)`)) {
      await api("DELETE", `/maquinas/${m.id}`);
      location.href = "maquinas.html";
      return;
    }
    if (!vacia && !confirmar(`¿Archivar "${m.nombre}"? Deja de aparecer en el listado y en Telegram; su historial se conserva.`)) return;
    await api("POST", `/maquinas/${m.id}/archivar`);
    avisar("Máquina archivada.");
    cargar();
  } catch (error) {
    avisar(error.message, "error");
  }
});

async function iniciar() {
  if (!MAQUINA_ID) {
    location.href = "maquinas.html";
    return;
  }
  opciones = await cargarOpciones();
  prepararFormMaquina(opciones);
  prepararFormVencimiento(opciones);
  llenarSelect(document.querySelector("[data-tipos-mantenimiento]"), opciones.tipos_mantenimiento);
  llenarSelect(document.querySelector("[data-tipos-trabajo]"), opciones.tipos_trabajo, "Elegí…");
  llenarSelect(document.getElementById("filtro-trabajos"), opciones.tipos_trabajo, "Todos los trabajos");
  llenarSelect(document.querySelector("[data-medidas]"), opciones.medidas_service);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
