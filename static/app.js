// Nombres "lindos" para mostrar cada categoría en pantalla.
const NOMBRES_CATEGORIA = {
  agroquimico: "🧪 Agroquímico",
  semilla: "🌱 Semilla",
  fertilizante: "🧂 Fertilizante",
  combustible: "⛽ Combustible",
  repuesto: "🔧 Repuesto",
  balanceado: "🌾 Balanceado",
  medicamento: "💉 Medicamento",
  otro: "📦 Otro",
};

// Unidades permitidas (las mismas que "Unidad" en main.py).
const UNIDADES = ["kg", "litros", "bolsas", "unidades"];

// Buscamos una sola vez los elementos del HTML que vamos a usar.
const estado = document.getElementById("estado");
const tabla = document.getElementById("tabla-stock");
const cuerpoTabla = document.getElementById("cuerpo-tabla");
const botonActualizar = document.getElementById("boton-actualizar");

const formInsumo = document.getElementById("form-insumo");
const inputNombre = document.getElementById("insumo-nombre");
const selectCategoria = document.getElementById("insumo-categoria");
const selectUnidad = document.getElementById("insumo-unidad");
const botonCrear = document.getElementById("boton-crear");
const mensajeInsumo = document.getElementById("mensaje-insumo");

const formMovimiento = document.getElementById("form-movimiento");
const selectInsumo = document.getElementById("movimiento-insumo");
const selectTipo = document.getElementById("movimiento-tipo");
const inputCantidad = document.getElementById("movimiento-cantidad");
const inputMotivo = document.getElementById("movimiento-motivo");
const botonRegistrar = document.getElementById("boton-registrar");
const mensajeMovimiento = document.getElementById("mensaje-movimiento");

// ---------- Ayudas generales ----------

// Muestra un número al estilo argentino: 1500.5 -> "1.500,5"
function formatearCantidad(numero) {
  return numero.toLocaleString("es-AR", { maximumFractionDigits: 2 });
}

// Crea una celda <td> con texto. Usamos textContent (y no innerHTML)
// para que nunca se ejecute código escondido en un nombre.
function crearCelda(texto, clase) {
  const celda = document.createElement("td");
  celda.textContent = texto;
  if (clase) {
    celda.className = clase;
  }
  return celda;
}

// Agrega una <option> a un <select>.
function agregarOpcion(select, valor, texto) {
  const opcion = document.createElement("option");
  opcion.value = valor; // Lo que se manda a la API: "agroquimico"
  opcion.textContent = texto; // Lo que ve el usuario: "🧪 Agroquímico"
  select.append(opcion);
}

// Muestra un mensaje debajo de un formulario. tipo = "ok" o "error".
function mostrarMensaje(elemento, texto, tipo) {
  elemento.textContent = texto;
  elemento.className = `mensaje ${tipo}`;
  elemento.hidden = false;
}

// Saca un texto entendible de una respuesta de error de FastAPI.
// - Errores nuestros (409, 404, 400): detail es un texto.
// - Errores de validación (422): detail es una lista de problemas.
//   Si el problema lo generó un validador nuestro (type "value_error"),
//   mostramos su mensaje; si no, mostramos el nombre del campo.
async function leerError(respuesta) {
  try {
    const datos = await respuesta.json();
    if (typeof datos.detail === "string") {
      return datos.detail;
    }
    if (Array.isArray(datos.detail)) {
      const problemas = datos.detail.map((problema) =>
        problema.type === "value_error"
          ? problema.msg.replace("Value error, ", "")
          : problema.loc.at(-1),
      );
      return `Revisá estos datos: ${problemas.join(", ")}`;
    }
  } catch {
    // La respuesta no era JSON: usamos el mensaje genérico de abajo.
  }
  return `El servidor respondió ${respuesta.status}`;
}

// ---------- Tabla de stock ----------

// Dibuja la tabla con la lista de insumos que vino de la API.
function mostrarInsumos(insumos) {
  cuerpoTabla.innerHTML = ""; // Vacía la tabla antes de volver a llenarla.

  if (insumos.length === 0) {
    estado.textContent = "No hay insumos cargados todavía.";
    tabla.hidden = true;
    return;
  }

  for (const insumo of insumos) {
    const fila = document.createElement("tr");
    const claseCantidad = insumo.cantidad === 0 ? "numero sin-stock" : "numero";

    fila.append(
      crearCelda(insumo.nombre),
      crearCelda(NOMBRES_CATEGORIA[insumo.categoria] || insumo.categoria),
      crearCelda(formatearCantidad(insumo.cantidad), claseCantidad),
      crearCelda(insumo.unidad),
    );
    cuerpoTabla.append(fila);
  }

  estado.textContent = `${insumos.length} insumos · actualizado ${new Date().toLocaleTimeString("es-AR")}`;
  tabla.hidden = false;
}

// Llena el desplegable de insumos del formulario de movimientos.
// Si había uno elegido, lo deja elegido (así no se pierde al refrescar).
function llenarSelectInsumos(insumos) {
  const elegido = selectInsumo.value;

  selectInsumo.length = 1; // Borra todas las opciones menos la primera ("Elegí…").
  // Ordenados por nombre (la API los manda por categoría) para encontrarlos fácil.
  const ordenados = [...insumos].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  for (const insumo of ordenados) {
    const texto = `${insumo.nombre} — ${formatearCantidad(insumo.cantidad)} ${insumo.unidad}`;
    agregarOpcion(selectInsumo, insumo.id, texto);
  }

  selectInsumo.value = elegido; // Si ya no existe, queda en "Elegí…".
}

// Pide los insumos a nuestra API y los muestra en la tabla y en el formulario.
async function cargarInsumos() {
  estado.className = "";
  estado.textContent = "Cargando…";

  try {
    const respuesta = await fetch("/insumos");
    if (!respuesta.ok) {
      throw new Error(`El servidor respondió ${respuesta.status}`);
    }
    const insumos = await respuesta.json();
    mostrarInsumos(insumos);
    llenarSelectInsumos(insumos);
  } catch (error) {
    estado.className = "error";
    estado.textContent = `⚠️ No se pudo cargar el stock (${error.message}). ¿Está corriendo el backend?`;
    tabla.hidden = true;
    console.error(error);
  }
}

// ---------- Formulario "Registrar movimiento" ----------

async function registrarMovimiento(evento) {
  evento.preventDefault(); // Que no recargue la página.

  const insumoId = selectInsumo.value;
  const tipo = selectTipo.value;
  const movimiento = {
    tipo: tipo,
    // Mandamos el texto tal cual ("2,5", "1.500"): la API lo interpreta
    // con la misma regla que usa Telegram.
    cantidad: inputCantidad.value.trim(),
    motivo: inputMotivo.value.trim() || "Web", // Como en Telegram, que pone "Telegram".
  };

  botonRegistrar.disabled = true;
  try {
    const respuesta = await fetch(`/insumos/${insumoId}/movimientos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(movimiento),
    });

    if (!respuesta.ok) {
      mostrarMensaje(mensajeMovimiento, `⚠️ ${await leerError(respuesta)}`, "error");
      return;
    }

    // La API devuelve el insumo con el stock ya actualizado.
    const insumo = await respuesta.json();
    const nombreTipo = tipo === "entrada" ? "Entrada" : "Salida";
    mostrarMensaje(
      mensajeMovimiento,
      `✅ ${nombreTipo} registrada en ${insumo.nombre}. Stock actual: ${formatearCantidad(insumo.cantidad)} ${insumo.unidad}`,
      "ok",
    );
    // Dejamos elegidos el insumo y el tipo (útil para cargar varios seguidos)
    // y vaciamos solo cantidad y motivo.
    inputCantidad.value = "";
    inputMotivo.value = "";
    inputCantidad.focus();
    cargarInsumos();
  } catch (error) {
    mostrarMensaje(mensajeMovimiento, "⚠️ No se pudo conectar con el servidor. ¿Está corriendo el backend?", "error");
    console.error(error);
  } finally {
    botonRegistrar.disabled = false;
  }
}

// ---------- Formulario "Nuevo insumo" ----------

// Llena los desplegables de categoría y unidad.
function prepararDesplegables() {
  for (const [valor, texto] of Object.entries(NOMBRES_CATEGORIA)) {
    agregarOpcion(selectCategoria, valor, texto);
  }
  for (const unidad of UNIDADES) {
    agregarOpcion(selectUnidad, unidad, unidad);
  }
}

// Se ejecuta al apretar "Crear" (o Enter dentro del formulario).
async function crearInsumo(evento) {
  // Por defecto, enviar un formulario RECARGA la página. Lo evitamos:
  // los datos los mandamos nosotros con fetch().
  evento.preventDefault();

  const insumoNuevo = {
    nombre: inputNombre.value.trim(),
    categoria: selectCategoria.value,
    unidad: selectUnidad.value,
  };

  // Desactivamos el botón mientras esperamos, para evitar doble clic.
  botonCrear.disabled = true;
  try {
    const respuesta = await fetch("/insumos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(insumoNuevo),
    });

    if (!respuesta.ok) {
      mostrarMensaje(mensajeInsumo, `⚠️ ${await leerError(respuesta)}`, "error");
      return;
    }

    const creado = await respuesta.json();
    mostrarMensaje(mensajeInsumo, `✅ Insumo creado: ${creado.nombre} (stock 0)`, "ok");
    formInsumo.reset(); // Vacía los campos.
    inputNombre.focus(); // Deja el cursor listo para cargar otro.
    await cargarInsumos(); // Refresca la tabla y el desplegable de movimientos.
    selectInsumo.value = creado.id; // Lo dejamos elegido para cargarle stock.
  } catch (error) {
    mostrarMensaje(mensajeInsumo, "⚠️ No se pudo conectar con el servidor. ¿Está corriendo el backend?", "error");
    console.error(error);
  } finally {
    // "finally" se ejecuta SIEMPRE: haya salido bien, mal o con return.
    botonCrear.disabled = false;
  }
}

// ---------- Inicio ----------

botonActualizar.addEventListener("click", cargarInsumos);
formInsumo.addEventListener("submit", crearInsumo);
formMovimiento.addEventListener("submit", registrarMovimiento);

// Al abrir la página: preparamos los formularios y cargamos los datos.
prepararDesplegables();
cargarInsumos();
