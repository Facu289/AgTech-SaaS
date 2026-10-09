// =========================================================
// ajustes.js — Apariencia (modo oscuro) y gestión de usuarios.
// =========================================================

// ---------- Apariencia ----------
// El tema lo maneja tema.js (window.temaAgroApp). Acá solo se elige.
const opcionesTema = document.getElementById("opciones-tema");
opcionesTema.querySelector(`input[value="${window.temaAgroApp.leer()}"]`).checked = true;
opcionesTema.addEventListener("change", (evento) => {
  window.temaAgroApp.guardar(evento.target.value);
  const nombres = { claro: "Claro", oscuro: "Oscuro", auto: "Automático" };
  avisar(`✅ Apariencia: ${nombres[evento.target.value]}`);
});

// ---------- Usuarios (solo admins) ----------
const seccionUsuarios = document.getElementById("seccion-usuarios");
const cuerpoUsuarios = document.getElementById("cuerpo-usuarios");
const formUsuario = document.getElementById("form-usuario");
const ventanaUsuario = document.getElementById("ventana-usuario");
const formContrasena = document.getElementById("form-contrasena");
const ventanaContrasena = document.getElementById("ventana-contrasena");

let yo = null;
let editandoId = null;      // null = creando uno nuevo
let contrasenaDeId = null;  // a quién le ponemos contraseña nueva

// "2026-10-08 22:51:31" -> "08/10/2026 22:51" (o "Nunca").
function textoIngreso(fecha) {
  return fecha ? formatearFechaHora(fecha) : "Nunca";
}

// Cómo puede entrar: con contraseña, con Google o con las dos.
function formasDeEntrar(u) {
  const formas = [];
  if (u.tiene_contrasena) formas.push(pill("Contraseña", "gris"));
  if (u.email) formas.push(pill("Google", "azul"));
  return el("div", { className: "grupo-pills" }, formas);
}

function mostrarUsuarios(usuarios) {
  cuerpoUsuarios.replaceChildren();
  for (const u of usuarios) {
    const esYo = u.id === yo.id;
    cuerpoUsuarios.append(
      el(
        "tr",
        { className: u.activo ? "" : "fila-archivada" },
        el("td", { className: "fuerte" }, u.nombre, esYo ? el("span", { className: "suave chico" }, " (vos)") : null),
        el("td", {}, u.email || "—"),
        el("td", {}, u.rol === "admin" ? pill("Admin", "violeta") : pill("Usuario", "gris")),
        el("td", {}, formasDeEntrar(u)),
        el("td", { className: "suave chico", style: "white-space:nowrap" }, textoIngreso(u.ultimo_ingreso)),
        el("td", {}, u.activo ? pill("Activo", "verde") : pill("Desactivado", "rojo")),
        el(
          "td",
          {},
          el(
            "div",
            { className: "acciones-fila" },
            botonIcono("lapiz", "Editar", { onclick: () => abrirEditar(u) }),
            botonIcono("llave", "Poner contraseña nueva", { onclick: () => abrirContrasena(u) }),
          ),
        ),
      ),
    );
  }
}

async function cargarUsuarios() {
  try {
    mostrarUsuarios(await api("GET", "/usuarios"));
  } catch (error) {
    cuerpoUsuarios.replaceChildren(filaVacia(7, `⚠️ ${error.message}`));
  }
}

// Algunos campos son solo para crear (contraseña) o solo para editar (activo).
function modoFormulario(nuevo) {
  for (const elemento of formUsuario.querySelectorAll("[data-solo-nuevo]")) elemento.hidden = !nuevo;
  for (const elemento of formUsuario.querySelectorAll("[data-solo-editar]")) elemento.hidden = nuevo;
  formUsuario.elements.contrasena.disabled = !nuevo;
}

function abrirNuevo() {
  editandoId = null;
  formUsuario.reset();
  modoFormulario(true);
  ventanaUsuario.querySelector("h2").textContent = "Nuevo usuario";
  abrirVentana(ventanaUsuario);
}

function abrirEditar(usuario) {
  editandoId = usuario.id;
  formUsuario.reset();
  modoFormulario(false);
  completarFormulario(formUsuario, usuario);
  ventanaUsuario.querySelector("h2").textContent = `Editar ${usuario.nombre}`;
  abrirVentana(ventanaUsuario);
}

function abrirContrasena(usuario) {
  contrasenaDeId = usuario.id;
  formContrasena.reset();
  ventanaContrasena.querySelector("h2").textContent = `Contraseña nueva para ${usuario.nombre}`;
  abrirVentana(ventanaContrasena);
}

formUsuario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const guardado = await enviarFormulario(formUsuario, (datos) => {
    if (editandoId) return api("PUT", `/usuarios/${editandoId}`, datos);
    return api("POST", "/usuarios", { ...datos, contrasena: datos.contrasena || null });
  });
  if (!guardado) return;
  ventanaUsuario.close();
  avisar(`✅ Guardado: ${guardado.nombre}`);
  cargarUsuarios();
});

formContrasena.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const listo = await enviarFormulario(formContrasena, async (datos) => {
    if (datos.contrasena !== datos.repetida) throw new Error("Las dos contraseñas no coinciden.");
    await api("POST", `/usuarios/${contrasenaDeId}/contrasena`, { contrasena: datos.contrasena });
    return true;
  });
  if (!listo) return;
  ventanaContrasena.close();
  avisar("✅ Contraseña cambiada. Se cerraron sus sesiones abiertas.");
  cargarUsuarios();
});

document.getElementById("boton-nuevo-usuario").addEventListener("click", abrirNuevo);

async function iniciar() {
  yo = await cargarYo();
  if (yo.rol !== "admin") {
    document.getElementById("aviso-no-admin").hidden = false;
    return;
  }
  seccionUsuarios.hidden = false;
  const google = await fetch("/auth/google/disponible").then((r) => r.json()).catch(() => ({ disponible: false }));
  document.getElementById("ayuda-google").textContent = google.disponible
    ? "Entrar con Google está activo: entra solo quien tenga su mail cargado acá y esté activo."
    : "Entrar con Google todavía no está configurado (faltan GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en el .env). Igual podés cargar los mails.";
  await cargarUsuarios();
}

iniciar();
