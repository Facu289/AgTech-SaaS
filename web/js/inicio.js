// =========================================================
// inicio.js — pantalla de Inicio: resumen y lo que requiere atención.
// =========================================================

const listaAtencion = document.getElementById("lista-atencion");
const estado = document.getElementById("estado");

function saludar() {
  const hora = new Date().getHours();
  const saludo = hora < 13 ? "Buen día" : hora < 20 ? "Buenas tardes" : "Buenas noches";
  document.getElementById("saludo").textContent = saludo;
  const fecha = new Date().toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  document.getElementById("fecha-hoy").textContent = fecha.charAt(0).toUpperCase() + fecha.slice(1);
}

function dato(href, valor, nombre, extra, extraEsAlerta = false) {
  return el(
    "a",
    { className: "dato", href },
    el("div", { className: "dato-valor" }, valor),
    el("div", { className: "dato-nombre" }, nombre),
    extra ? el("div", { className: `dato-extra${extraEsAlerta ? " alerta-texto" : ""}` }, extra) : null,
  );
}

function mostrarResumen(insumos, maquinas, animales, alertas) {
  const activos = animales.filter((a) => a.estado === "activo");
  const prenadas = activos.filter((a) => a.estado_reproductivo === "prenada").length;
  const services = alertas.services.length;
  // Un cuadro por página de stock: Insumos, Químicos y Repuestos.
  const datoStock = (hoja, nombre) => {
    const cantidad = insumos.filter((i) => i.hoja === hoja).length;
    const bajos = alertas.stock_bajo.filter((i) => i.hoja === hoja).length;
    return dato(`${hoja}.html`, cantidad, nombre, bajos ? `${bajos} bajo el mínimo` : "Stock en orden", bajos > 0);
  };
  document.getElementById("resumen").replaceChildren(
    datoStock("insumos", "Insumos"),
    datoStock("quimicos", "Químicos"),
    datoStock("repuestos", "Repuestos"),
    dato("maquinas.html", maquinas.length, "Máquinas", services ? `${services} service(s) para hacer` : "Services al día", services > 0),
    dato("animales.html", activos.reduce((total, a) => total + a.cantidad, 0), "Animales activos", `${prenadas} preñada${prenadas === 1 ? "" : "s"}`),
  );
}

// Una fila de "Requiere atención".
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
  listaAtencion.replaceChildren(...items.map((i) => i.nodo));
  if (items.length === 0) {
    listaAtencion.append(el("li", {}, el("div", { className: "texto-atencion suave" }, "✓ Todo en orden: no hay vencimientos, services, partos ni stock bajo para revisar.")));
  }
  estado.textContent = items.length ? `${items.length} para revisar` : "";
}

function mostrarUltimos(movimientos) {
  const lista = document.getElementById("ultimos-movimientos");
  lista.replaceChildren(
    ...movimientos.map((m) => {
      const entrada = m.tipo === "entrada";
      return el(
        "li",
        {},
        el("div", { className: "texto-atencion" }, el("div", { className: "fuerte" }, m.insumo_nombre), el("div", { className: "suave chico" }, `${formatearFechaHora(m.fecha)}${m.motivo ? ` · ${m.motivo}` : ""}`)),
        el("span", { className: "numero fuerte", style: `color:${entrada ? "var(--acento-texto)" : "var(--ambar)"}` }, `${entrada ? "+" : "−"}${formatearCantidad(m.cantidad)} ${m.unidad}`),
      );
    }),
  );
  if (movimientos.length === 0) lista.append(el("li", { className: "suave" }, "Todavía no hay movimientos."));
}

async function cargar() {
  try {
    const [insumos, maquinas, animales, alertas, movimientos] = await Promise.all([
      api("GET", "/insumos"),
      api("GET", "/maquinas"),
      api("GET", "/animales"),
      api("GET", "/alertas"),
      api("GET", "/movimientos?limite=6"),
    ]);
    mostrarResumen(insumos, maquinas, animales, alertas);
    mostrarAtencion(alertas);
    mostrarUltimos(movimientos);
  } catch (error) {
    estado.textContent = `⚠️ ${error.message}`;
  }
}

saludar();
cargar();
refrescarAutomaticamente(cargar);
