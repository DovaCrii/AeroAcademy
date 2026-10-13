// Mejora progresiva: botón «mostrar/ocultar contraseña». Sin JS el campo funciona igual.
(function () {
  "use strict";
  var EYE = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  document.querySelectorAll(".ico-wrap input[type=password]").forEach(function (input) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "eye";
    btn.setAttribute("aria-label", "Mostrar contraseña");
    btn.setAttribute("aria-pressed", "false");
    btn.innerHTML = EYE;
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
    });
    input.parentNode.appendChild(btn);
    input.classList.add("has-eye");
  });
})();
