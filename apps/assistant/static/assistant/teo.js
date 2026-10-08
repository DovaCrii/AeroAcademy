/* Widget de Teo: envía la pregunta por fetch y muestra la respuesta sin recargar.
   Sin JS, el formulario hace un POST normal a /teo/ y funciona igual. */
(function () {
  "use strict";
  var form = document.querySelector("[data-teo-form]");
  if (!form || !window.fetch) return;
  var out = document.querySelector("[data-teo-answer]");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var button = form.querySelector("button");
    button.disabled = true;
    out.textContent = "Teo está midiendo…";
    fetch(form.getAttribute("data-endpoint"), {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "fetch" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.text(); })
      .then(function (html) { out.innerHTML = html; })
      .catch(function () { out.textContent = "Se me empañó el lente, intenta de nuevo en un rato."; })
      .then(function () { button.disabled = false; });
  });
})();
