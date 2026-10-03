// =========================================================
// login.js — página de entrada. No usa comun.js (esa página
// arma el menú y pide datos, y acá todavía no entraste).
// =========================================================

const formulario = document.querySelector("#form-login");
const mensaje = formulario.querySelector(".mensaje");
const boton = formulario.querySelector('button[type="submit"]');

// La hojita del logo (mismo dibujo que en comun.js).
document.querySelector("#logo-icono").innerHTML =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21V11"/>' +
  '<path d="M12 11C12 7 9 4.5 4.5 4.5 4.5 9 7.5 11 12 11Z"/><path d="M12 13c0-3.5 2.6-6 7.5-6 0 4.5-3 6-7.5 6Z"/></svg>';

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mensaje.hidden = true;
  boton.disabled = true;
  const datos = Object.fromEntries(new FormData(formulario));
  try {
    const respuesta = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: datos.usuario.trim(), contrasena: datos.contrasena }),
    });
    if (respuesta.ok) {
      // La cookie de sesión ya quedó guardada (el navegador lo hace solo). Vamos al Inicio.
      location.href = "index.html";
      return;
    }
    const error = await respuesta.json().catch(() => ({}));
    mostrarError(typeof error.detail === "string" ? error.detail : "No se pudo entrar.");
  } catch {
    mostrarError("No se pudo conectar con el servidor. ¿Está corriendo el backend?");
  } finally {
    boton.disabled = false;
  }
});

function mostrarError(texto) {
  mensaje.textContent = `⚠️ ${texto}`;
  mensaje.hidden = false;
  formulario.contrasena.value = "";
  formulario.contrasena.focus();
}
