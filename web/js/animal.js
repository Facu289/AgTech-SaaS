// =========================================================
// animal.js — ficha de UN animal (animal.html?id=5).
// =========================================================

const ANIMAL_ID = new URLSearchParams(location.search).get("id");
const titulo = document.getElementById("titulo");
const formEvento = document.getElementById("form-evento");

let opciones = null;
let ficha = null; // { animal, eventos, crias }
let creandoCria = false;
let reproductivaAnterior = null;

function dato(valor, nombre) {
  return el("div", { className: "dato" }, el("div", { className: "dato-valor" }, valor), el("div", { className: "dato-nombre" }, nombre));
}

function mostrarFicha() {
  const a = ficha.animal;
  const nombre = `${a.es_grupo ? "Grupo" : "Caravana"} ${a.caravana}`;
  document.title = `${nombre} · AgroApp`;
  titulo.replaceChildren(`${nombre} `, pillEspecie(a), " ", pill(a.categoria));
  if (a.estado !== "activo") titulo.append(" ", pill(opciones.estados_animal[a.estado], "gris"));
  document.getElementById("subtitulo").textContent = [a.raza, a.rodeo && `rodeo ${a.rodeo}`, edad(a.fecha_nacimiento)].filter(Boolean).join(" · ");
  document.getElementById("acciones-ficha").hidden = false;

  const resumen = document.getElementById("resumen");
  resumen.replaceChildren();
  if (a.es_grupo) resumen.append(dato(formatearCantidad(a.cantidad), "Animales en el grupo"));
  if (a.reproductiva) {
    resumen.append(dato(opciones.estados_reproductivos[a.estado_reproductivo], "Estado reproductivo"));
    if (a.fecha_probable_parto) {
      resumen.append(dato(formatearFecha(a.fecha_probable_parto), `Parto probable · ${describirDias(diasHasta(a.fecha_probable_parto))}`));
    }
    resumen.append(dato(a.partos, a.partos === 1 ? "Parto registrado" : "Partos registrados"));
  }
  resumen.append(dato(ficha.eventos.length, "Eventos"));

  const campos = [
    ["Especie", a.especie],
    ["Categoría", a.categoria],
    ...(a.es_grupo ? [["Cantidad", formatearCantidad(a.cantidad)]] : []),
    ["Raza", a.raza],
    ["Rodeo", a.rodeo],
    ["Nacimiento", a.fecha_nacimiento ? `${formatearFecha(a.fecha_nacimiento)} (${edad(a.fecha_nacimiento)})` : ""],
    ["Madre", a.madre_caravana],
    ["Situación", opciones.estados_animal[a.estado]],
    ["Cargado el", formatearFecha(a.creado_en)],
    ["Observaciones", a.observaciones],
  ];
  const datos = document.getElementById("datos");
  datos.replaceChildren(
    // Cada par (nombre, valor) va en su propio <div>, así queda alineado en la grilla.
    ...campos.map(([nombre, valor]) => {
      let contenido = valor || "—";
      if (nombre === "Madre" && a.madre_id) contenido = el("a", { href: `animal.html?id=${a.madre_id}` }, valor);
      return el("div", {}, el("dt", {}, nombre), el("dd", {}, contenido));
    }),
  );

  // Eventos: solo si está activo.
  document.getElementById("tarjeta-evento").hidden = a.estado !== "activo";
  // Crías: solo de una hembra suelta (no de un grupo).
  document.getElementById("tarjeta-crias").hidden = !(a.sexo === "hembra" && !a.es_grupo);
  // Si hay eventos, no se puede eliminar (se da de baja editando la situación).
  const botonEliminar = document.getElementById("boton-eliminar");
  botonEliminar.hidden = ficha.eventos.length > 0 || ficha.crias.length > 0;
}

function mostrarEventos() {
  const cuerpo = document.getElementById("tabla-eventos");
  cuerpo.replaceChildren();
  if (ficha.eventos.length === 0) cuerpo.append(filaVacia(4, "Sin eventos registrados."));
  const colores = { parto: "verde", aborto: "rojo", tacto: "azul", servicio: "violeta", sanidad: "", observacion: "gris" };
  for (const e of ficha.eventos) {
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", { style: "white-space:nowrap" }, formatearFecha(e.fecha)),
        el("td", {}, pill(opciones.tipos_evento[e.tipo] ?? e.tipo, colores[e.tipo] ?? "")),
        el("td", {}, describirEvento(e) || el("span", { className: "suave" }, "—")),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("basura", "Eliminar evento", {
              className: "peligro",
              onclick: async () => {
                if (!confirmar("¿Eliminar este evento? No deshace el cambio de estado del animal.")) return;
                try {
                  await api("DELETE", `/eventos-animales/${e.id}`);
                  cargar();
                } catch (error) {
                  avisar(error.message, "error");
                }
              },
            }),
          ),
        ),
      ),
    );
  }
}

function mostrarCrias() {
  const cuerpo = document.getElementById("tabla-crias");
  cuerpo.replaceChildren();
  if (ficha.crias.length === 0) cuerpo.append(filaVacia(4, "Sin crías cargadas con caravana."));
  for (const c of ficha.crias) {
    cuerpo.append(
      el(
        "tr",
        {},
        el("td", {}, el("a", { href: `animal.html?id=${c.id}`, className: "fuerte" }, c.caravana)),
        el("td", {}, c.categoria),
        el("td", {}, c.fecha_nacimiento ? `${formatearFecha(c.fecha_nacimiento)} (${edad(c.fecha_nacimiento)})` : "—"),
        el("td", {}, opciones.estados_animal[c.estado]),
      ),
    );
  }
}

async function cargar() {
  try {
    const [datos, animales] = await Promise.all([api("GET", `/animales/${ANIMAL_ID}`), api("GET", "/animales"), cargarEspecies()]);
    ficha = datos;
    actualizarListasAnimal(animales);
  } catch (error) {
    titulo.textContent = "No se pudo cargar el animal";
    document.getElementById("subtitulo").textContent = error.message;
    return;
  }
  mostrarFicha();
  // Si cambió (ej: se editó la categoría), se rehacen los tipos de evento posibles.
  if (ficha.animal.reproductiva !== reproductivaAnterior) {
    reproductivaAnterior = ficha.animal.reproductiva;
    prepararFormEvento(opciones, !ficha.animal.reproductiva);
  }
  mostrarEventos();
  mostrarCrias();
}

formEvento.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const actualizado = await enviarFormulario(formEvento, (datos) => api("POST", `/animales/${ANIMAL_ID}/eventos`, datos));
  if (!actualizado) return;
  avisar(`✅ ${opciones.tipos_evento[formEvento.elements.tipo.value]} registrado.`);
  reiniciarFormEvento();
  cargar();
});

document.getElementById("boton-editar").addEventListener("click", () => {
  creandoCria = false;
  abrirVentanaAnimal(ficha.animal);
});

document.getElementById("boton-cria").addEventListener("click", () => {
  creandoCria = true;
  // La cría es de la misma especie; la categoría se elige (ternera, cordero, lechón...).
  abrirVentanaAnimal(null, {
    especie_id: ficha.animal.especie_id,
    madre_id: ficha.animal.id,
    rodeo: ficha.animal.rodeo,
    raza: ficha.animal.raza,
    fecha_nacimiento: hoyISO(),
    estado: "activo",
  });
});

document.getElementById("form-animal").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await guardarAnimal(creandoCria ? null : ANIMAL_ID);
  if (!guardado) return;
  document.getElementById("ventana-animal").close();
  avisar(creandoCria ? `✅ Cría ${guardado.caravana} cargada.` : "✅ Datos guardados.");
  cargar();
});

document.getElementById("boton-eliminar").addEventListener("click", async () => {
  if (!confirmar(`¿Eliminar la caravana ${ficha.animal.caravana}? No se puede deshacer.`)) return;
  try {
    await api("DELETE", `/animales/${ANIMAL_ID}`);
    location.href = "animales.html";
  } catch (error) {
    avisar(error.message, "error");
  }
});

async function iniciar() {
  if (!ANIMAL_ID) {
    location.href = "animales.html";
    return;
  }
  opciones = await cargarOpciones();
  await cargarEspecies();
  prepararFormAnimal(opciones);
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
