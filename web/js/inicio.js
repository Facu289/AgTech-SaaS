// =========================================================
// inicio.js — el tablero de Inicio:
//   números principales · mapa general · accesos rápidos · última orden de trabajo
//   · última actividad · lo que requiere atención.
// =========================================================

const listaAtencion = document.getElementById("lista-atencion");
const estado = document.getElementById("estado");
const MAXIMO_ATENCION = 6; // Lo demás se ve en cada sección (el Inicio tiene que ser corto).

let opciones = null;

function saludar() {
  const hora = new Date().getHours();
  const saludo = hora < 13 ? "Buen día" : hora < 20 ? "Buenas tardes" : "Buenas noches";
  document.getElementById("saludo").textContent = saludo;
  const fecha = new Date().toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  document.getElementById("fecha-hoy").textContent = fecha.charAt(0).toUpperCase() + fecha.slice(1);
}

// ---------- Números principales ----------

function dato(href, valor, nombre, extra, extraEsAlerta = false) {
  return el(
    "a",
    { className: "dato", href },
    el("div", { className: "dato-valor" }, valor),
    el("div", { className: "dato-nombre" }, nombre),
    extra ? el("div", { className: `dato-extra${extraEsAlerta ? " alerta-texto" : ""}` }, extra) : null,
  );
}

function mostrarResumen(insumos, maquinas, animales, alertas, lotes) {
  const activos = animales.filter((a) => a.estado === "activo");
  const prenadas = activos.filter((a) => a.estado_reproductivo === "prenada").length;
  const services = alertas.services.length;
  const pendientes = alertas.ordenes_pendientes.length;
  const sinStock = alertas.ordenes_pendientes.filter((o) => o.faltantes.length).length;
  // Un cuadro por página de stock: Químicos, Insumos y Repuestos.
  const datoStock = (hoja, nombre) => {
    const cantidad = insumos.filter((i) => i.hoja === hoja).length;
    const bajos = alertas.stock_bajo.filter((i) => i.hoja === hoja).length;
    return dato(`${hoja}.html`, cantidad, nombre, bajos ? `${bajos} bajo el mínimo` : "Stock en orden", bajos > 0);
  };
  document.getElementById("resumen").replaceChildren(
    dato("lotes.html", lotes.length, "Lotes", `${formatearCantidad(lotes.reduce((total, l) => total + (l.hectareas || 0), 0))} ha`),
    dato("ordenes.html?estado=pendiente", pendientes, "Órdenes pendientes", sinStock ? `${sinStock} sin stock suficiente` : "Stock alcanza", sinStock > 0),
    datoStock("quimicos", "Químicos"),
    datoStock("insumos", "Insumos"),
    dato("maquinas.html", maquinas.length, "Máquinas", services ? `${services} service(s) para hacer` : "Services al día", services > 0),
    dato("animales.html", activos.reduce((total, a) => total + a.cantidad, 0), "Animales activos", `${prenadas} preñada${prenadas === 1 ? "" : "s"}`),
  );
}

// ---------- Requiere atención (compacto) ----------

function itemAtencion(nombreIcono, texto, detalle, href, urgente) {
  const iconoCaja = el("span", { className: "icono-atencion" });
  iconoCaja.innerHTML = icono(nombreIcono, 16);
  return el(
    "li",
    {},
    iconoCaja,
    el("div", { className: "texto-atencion" }, el("div", { className: "fuerte" }, texto), el("div", { className: "suave chico" }, detalle)),
    pill(urgente ? "Urgente" : "Pronto", urgente ? "rojo" : "ambar"),
    el("a", { href, className: "boton-tabla" }, "Ver"),
  );
}

function mostrarAtencion(alertas) {
  const items = [];
  for (const o of alertas.ordenes_pendientes.filter((o) => o.faltantes.length)) {
    items.push({ orden: -2000, nodo: itemAtencion("orden", `OT ${o.numero || o.id}: falta stock`, `Falta ${o.faltantes.join(", ")}`, `orden.html?id=${o.id}`, true) });
  }
  for (const v of alertas.vencimientos) {
    items.push({ orden: v.dias, nodo: itemAtencion("calendario", `${v.descripcion}${v.maquina_nombre ? ` · ${v.maquina_nombre}` : ""}`, `${v.dias < 0 ? "Venció" : "Vence"} ${describirDias(v.dias)} (${formatearFecha(v.fecha_vencimiento)})`, "vencimientos.html", v.dias < 0) });
  }
  for (const s of alertas.services) {
    const texto = s.faltan < 0 ? `pasado por ${formatearCantidad(-s.faltan)} h` : `faltan ${formatearCantidad(s.faltan)} h`;
    items.push({ orden: s.faltan < 0 ? -1000 : 5, nodo: itemAtencion("llave", `${s.nombre} · ${s.maquina_nombre}`, `Service cada ${formatearCantidad(s.cada_horas)} h: ${texto}`, `maquina.html?id=${s.maquina_id}`, s.faltan < 0) });
  }
  for (const p of alertas.partos) {
    items.push({ orden: p.dias, nodo: itemAtencion("vaca", `Parto · caravana ${p.caravana}${p.especie === "Vacuno" ? "" : ` (${p.especie})`}`, `${describirDias(p.dias)} (${formatearFecha(p.fecha_probable_parto)})${p.rodeo ? ` · rodeo ${p.rodeo}` : ""}`, `animal.html?id=${p.id}`, p.dias < 0) });
  }
  for (const i of alertas.stock_bajo) {
    items.push({ orden: 10, nodo: itemAtencion("caja", `Stock bajo · ${i.nombre}`, `Quedan ${formatearCantidad(i.cantidad)} ${i.unidad} (mínimo ${formatearCantidad(i.stock_minimo)})`, `${i.hoja}.html?stock=bajo`, i.cantidad === 0) });
  }
  items.sort((a, b) => a.orden - b.orden);
  listaAtencion.replaceChildren(...items.slice(0, MAXIMO_ATENCION).map((i) => i.nodo));
  if (items.length > MAXIMO_ATENCION) {
    listaAtencion.append(el("li", { className: "suave chico" }, `Y ${items.length - MAXIMO_ATENCION} más (mirá cada sección o los números de la barra lateral).`));
  }
  if (items.length === 0) {
    listaAtencion.append(el("li", {}, el("div", { className: "texto-atencion suave" }, "✓ Todo en orden: no hay vencimientos, services, partos, stock bajo ni órdenes sin stock.")));
  }
  estado.textContent = items.length ? `${items.length} para revisar` : "";
}

// ---------- Última orden de trabajo ----------

const COLOR_ESTADO = { pendiente: "ambar", realizada: "verde", anulada: "gris" };

function mostrarUltimaOrden(ordenes) {
  const caja = document.getElementById("ultima-orden");
  const o = ordenes[0];
  if (!o) {
    caja.replaceChildren(el("p", { className: "suave" }, "Todavía no hay órdenes. ", el("a", { href: "orden.html" }, "Cargá la primera")));
    return;
  }
  const lotes = o.lotes.map((l) => l.lote).join(", ");
  caja.replaceChildren(
    el(
      "div",
      { className: "ultima-orden" },
      el("div", { className: "ultima-orden-cabeza" },
        el("a", { className: "fuerte", href: `orden.html?id=${o.id}` }, o.numero ? `OT ${o.numero}` : `Orden #${o.id}`),
        pill(opciones.estados_orden[o.estado], COLOR_ESTADO[o.estado])),
      el("div", { className: "suave chico" },
        [formatearFecha(o.fecha_emision), opciones.tareas_orden[o.tarea], o.campo].filter(Boolean).join(" · ")),
      el("div", {}, `${lotes || "Sin lotes"} · ${formatearCantidad(o.hectareas)} ha`),
      el("ul", { className: "ultima-orden-productos" },
        o.productos.map((p) => el("li", {}, el("span", {}, p.insumo), el("span", { className: "suave" }, `${formatearCantidad(p.cantidad_total)} ${p.unidad}`)))),
      o.advertencias.length ? el("p", { className: "mensaje advertencia chico" }, `⚠️ ${o.advertencias[0]}`) : null,
      el("div", { className: "acciones-fila", style: "justify-content:flex-start" },
        el("a", { className: "boton boton-secundario", href: `orden.html?id=${o.id}` }, o.estado === "pendiente" ? "Abrir / marcar realizada" : "Abrir")),
    ),
  );
}

// ---------- Última actividad ----------

const ICONO_ACTIVIDAD = { orden: "orden", stock: "flechas", maquina: "tractor", animal: "vaca", lote: "hoja" };

function mostrarActividad(actividad) {
  const lista = document.getElementById("ultima-actividad");
  lista.replaceChildren(
    ...actividad.map((a) => {
      const iconoCaja = el("span", { className: "icono-atencion" });
      iconoCaja.innerHTML = icono(ICONO_ACTIVIDAD[a.tipo] || "lista", 16);
      return el(
        "li",
        {},
        iconoCaja,
        el("div", { className: "texto-atencion" },
          el("a", { className: "fuerte enlace-sin-linea", href: a.enlace }, a.titulo),
          el("div", { className: "suave chico" }, [formatearFechaHora(a.momento), a.detalle].filter(Boolean).join(" · "))),
      );
    }),
  );
  if (actividad.length === 0) lista.append(el("li", { className: "suave" }, "Todavía no hay nada cargado."));
}

// ---------- Mapa general ----------
// La misma campaña que estás mirando en la página Lotes (o la más nueva).

const contenedorMapa = document.getElementById("mapa-inicio");
// Sin zoom con la rueda: si no, al bajar por la página el mapa se agranda sin querer.
const mapa = hayMapa(contenedorMapa) ? crearMapaSatelital(contenedorMapa, { scrollWheelZoom: false }) : null;
const capaLotes = mapa ? L.featureGroup().addTo(mapa) : null;
let mapaEncuadrado = false;

async function cargarLotes() {
  const campanias = await api("GET", "/campanias");
  const campania = campaniaRecordada(campanias);
  const lotes = await api("GET", `/lotes${campania ? `?campania_id=${campania.id}` : ""}`);
  document.getElementById("campania-inicio").textContent = campania ? `Campaña ${campania.nombre}` : "";
  if (mapa) {
    // Tocar un lote abre su ficha.
    dibujarLotes(capaLotes, lotes, { alHacerClic: (lote) => (location.href = `lote.html?id=${lote.id}`) });
    if (!mapaEncuadrado && capaLotes.getLayers().length) {
      mapa.fitBounds(capaLotes.getBounds(), { padding: [16, 16], maxZoom: 16 });
      mapaEncuadrado = true;
    }
  }
  const leyenda = document.getElementById("leyenda-inicio");
  if (lotes.length === 0) {
    leyenda.replaceChildren(el("p", { className: "suave" }, "Todavía no dibujaste lotes. ", el("a", { href: "lotes.html" }, "Dibujá el primero o importá un KMZ")));
  } else {
    leyenda.replaceChildren(armarLeyenda(lotes));
  }
  return lotes;
}

// ---------- Cargar todo ----------

async function cargar() {
  try {
    const [insumos, maquinas, animales, alertas, lotes, ordenes, actividad] = await Promise.all([
      api("GET", "/insumos"),
      api("GET", "/maquinas"),
      api("GET", "/animales"),
      api("GET", "/alertas"),
      cargarLotes(),
      api("GET", "/ordenes"),
      api("GET", "/actividad?limite=8"),
    ]);
    mostrarResumen(insumos, maquinas, animales, alertas, lotes);
    mostrarUltimaOrden(ordenes);
    mostrarActividad(actividad);
    mostrarAtencion(alertas);
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

async function iniciar() {
  saludar();
  opciones = await cargarOpciones();
  await cargar();
  refrescarAutomaticamente(cargar);
}

iniciar();
