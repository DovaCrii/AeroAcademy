/* Widget de Teo: envía la pregunta (o un atajo) por fetch y muestra la respuesta sin recargar.
   Sin JS, los formularios hacen un POST normal a /teo/ y funcionan igual. */
(function () {
  "use strict";
  if (!window.fetch) return;
  var out = document.querySelector("[data-teo-answer]");
  document.querySelectorAll("[data-teo-form]").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (!out) return; // en la página completa, el envío normal basta
      ev.preventDefault();
      var data = new FormData(form);
      var submitter = ev.submitter;
      if (submitter && submitter.name) data.append(submitter.name, submitter.value);
      var buttons = form.querySelectorAll("button");
      buttons.forEach(function (b) { b.disabled = true; });
      out.textContent = "Nala está olfateando…";
      fetch(form.getAttribute("data-endpoint"), {
        method: "POST",
        body: data,
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      })
        .then(function (r) { return r.text(); })
        .then(function (html) { out.innerHTML = html; })
        .catch(function () { out.textContent = "Se me empañó el lente, intenta de nuevo en un rato."; })
        .then(function () { buttons.forEach(function (b) { b.disabled = false; }); });
    });
  });
})();
