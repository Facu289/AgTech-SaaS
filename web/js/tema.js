// =========================================================
// tema.js — modo claro / oscuro (Ajustes > Apariencia).
// Va en el <head> de TODAS las páginas, ANTES del CSS y sin "defer":
// así el color se decide antes de dibujar y no hay un "flash" blanco.
//
// Se guarda en ESTE navegador (localStorage): cada celular o PC tiene el suyo.
//   "claro" | "oscuro" | "auto" (sigue al celular / PC)
// =========================================================
(function () {
  const CLAVE = "agroapp-tema";
  const POR_DEFECTO = "claro"; // Sin elegir nada, se ve como siempre.
  const sistemaOscuro = window.matchMedia("(prefers-color-scheme: dark)");

  // localStorage puede fallar (modo incógnito, permisos): por eso try/catch.
  function leer() {
    try {
      const valor = localStorage.getItem(CLAVE);
      return ["claro", "oscuro", "auto"].includes(valor) ? valor : POR_DEFECTO;
    } catch {
      return POR_DEFECTO;
    }
  }

  function aplicar() {
    const elegido = leer();
    const oscuro = elegido === "oscuro" || (elegido === "auto" && sistemaOscuro.matches);
    document.documentElement.dataset.tema = oscuro ? "oscuro" : "claro";
  }

  function guardar(valor) {
    try {
      localStorage.setItem(CLAVE, valor);
    } catch {
      // Si no se puede guardar, igual se aplica en esta página.
    }
    aplicar();
  }

  // En "auto", si el celular pasa a modo noche, la página cambia sola.
  sistemaOscuro.addEventListener("change", aplicar);
  // Si se cambia en otra pestaña, se actualiza también acá.
  window.addEventListener("storage", (evento) => {
    if (evento.key === CLAVE) aplicar();
  });
  // Al imprimir, siempre en claro (papel blanco, tinta negra).
  window.addEventListener("beforeprint", () => (document.documentElement.dataset.tema = "claro"));
  window.addEventListener("afterprint", aplicar);

  aplicar();
  window.temaAgroApp = { leer, guardar };
})();
