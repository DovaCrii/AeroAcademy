/* Mejora progresiva del editor de avatar. Sin este archivo todo funciona igual (el servidor hace lo mismo al guardar).
   1. Al elegir una carrera, marca las opciones de su look (ropa, gorro, lentes, herramienta, fondo…) para que la
      vista previa en vivo y lo que se guarda coincidan con lo que se ve.
   2. Acordeón: recuerda la sección abierta (campo oculto y enlaces de «Sorpréndeme» y «Restablecer») y, en navegadores
      sin `<details name>`, cierra las otras al abrir una.
   3. Resumen de cada sección y nombre de la opción elegida al día, y aviso de «Cambios sin guardar».
   4. «Sorpréndeme»: hace rodar el dado un instante antes de cambiar de página (si la persona acepta animaciones). */
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

  // --- acordeón ---
  var current = document.getElementById("avSeccion");
  var sections = Array.prototype.slice.call(form.querySelectorAll("details.av-sec"));
  var nativeGroup = "name" in HTMLDetailsElement.prototype;
  var links = Array.prototype.slice.call(form.querySelectorAll(".av-more a"));
  sections.forEach(function (sec) {
    sec.addEventListener("toggle", function () {
      if (!sec.open) return;
      if (!nativeGroup) {
        sections.forEach(function (other) {
          if (other !== sec) other.open = false;
        });
      }
      if (current) current.value = sec.getAttribute("data-slug") || "";
      links.forEach(function (a) {
        a.href = a.href.replace(/([?&]seccion=)[^&]*/, "$1" + encodeURIComponent(current.value));
      });
    });
  });

  // --- resumen de cada sección, nombre de lo elegido y aviso de cambios ---
  function labelOf(input) {
    return input ? input.getAttribute("data-label") || input.getAttribute("aria-label") || "" : "";
  }
  function refresh() {
    form.querySelectorAll("fieldset.av-group").forEach(function (fs) {
      var cur = fs.querySelector(".av-cur");
      if (cur) cur.textContent = labelOf(fs.querySelector("input:checked"));
    });
    sections.forEach(function (sec) {
      var spec = [];
      try {
        spec = JSON.parse(sec.getAttribute("data-sum") || "[]");
      } catch (e) {
        return;
      }
      var parts = [];
      spec.forEach(function (item) {
        var checked = form.querySelector('input[name="' + item[0] + '"]:checked');
        var label = labelOf(checked);
        if (label) parts.push(item[1].replace("{}", label));
      });
      var out = sec.querySelector(".av-sum");
      if (out && parts.length) out.textContent = parts.join(", ");
    });
  }
  var dirty = form.querySelector(".av-dirty");
  form.addEventListener("change", function (event) {
    if (!event.target || event.target.type !== "radio") return;
    refresh();
    if (dirty) dirty.hidden = false;
  });
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
