/* Botón «Imprimir» del diploma (sin JavaScript en línea). */
(function () {
  "use strict";
  var button = document.querySelector("[data-print]");
  if (button) button.addEventListener("click", function () { window.print(); });
})();
