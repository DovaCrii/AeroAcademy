/* Mejora progresiva del editor de avatar. Sin este archivo todo funciona igual (el servidor hace lo mismo al guardar).
   1. Al elegir una carrera, marca las opciones de su look (ropa, gorro, lentes, herramienta, fondo…) para que la
      vista previa en vivo y lo que se guarda coincidan con lo que se ve.
   2. «Sorpréndeme»: hace rodar el dado un instante antes de cambiar de página (si la persona acepta animaciones). */
(function () {
  "use strict";
  var form = document.getElementById("avForm");
  if (!form) return;

  // Fase de captura: corre antes que la vista previa en vivo (enhance.js), que lee el formulario ya actualizado.
  form.addEventListener(
    "change",
    function (event) {
      var input = event.target;
      if (!input || input.name !== "class" || !input.checked) return;
      var look = {};
      try {
        look = JSON.parse(input.getAttribute("data-look") || "{}");
      } catch (e) {
        return;
      }
      Object.keys(look).forEach(function (key) {
        var wanted = form.querySelector(
          'input[name="' + key + '"][value="' + String(look[key]).replace(/"/g, "") + '"]'
        );
        if (wanted && !wanted.disabled) wanted.checked = true;
      });
    },
    true
  );

  var dice = form.querySelector(".av-dice");
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (dice && !calm) {
    dice.addEventListener("click", function (event) {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.button) return;
      event.preventDefault();
      dice.classList.add("rolling");
      window.setTimeout(function () {
        window.location.href = dice.href;
      }, 450);
    });
  }
})();
