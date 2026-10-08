/* Mejora progresiva (equivalente local de HTMX).
   - `[data-enhance-root]`: región que se reemplaza completa (ruta interactiva).
   - Formularios y enlaces con `data-enhance`: se envían por fetch con la cabecera `X-Partial`.
   - `data-target="#id"`: en vez de la región completa, reemplaza solo ese elemento (vista previa del avatar).
   - `data-live`: el formulario se envía solo al cambiar cualquier campo (vista previa en vivo).
   Sin JS, todo funciona con formularios y enlaces normales. */
(function () {
  "use strict";
  var root = document.querySelector("[data-enhance-root]");
  if (!root || !window.fetch) return;

  function focusAgain(id) {
    if (!id) return;
    var el = root.querySelector('[data-fid="' + id + '"]');
    if (el) el.focus({ preventScroll: true });
  }

  function swap(html, target, focusId) {
    (target || root).innerHTML = html;
    focusAgain(focusId);
  }

  function request(url, options, target, focusId, fallback) {
    options.headers = { "X-Partial": "1", "X-Requested-With": "fetch" };
    options.credentials = "same-origin";
    return fetch(url, options)
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.text();
      })
      .then(function (html) { swap(html, target, focusId); return true; })
      .catch(function () { fallback(); });
  }

  function targetOf(el) {
    var sel = el.getAttribute("data-target");
    return sel ? document.querySelector(sel) : null;
  }

  function send(form) {
    var active = document.activeElement;
    var focusId = active && active.dataset ? active.dataset.fid : null;
    var target = targetOf(form);
    if ((form.method || "get").toLowerCase() === "get") {
      var query = new URLSearchParams(new FormData(form)).toString();
      return request(form.action + "?" + query, { method: "GET" }, target, focusId, function () {});
    }
    return request(form.action, { method: "POST", body: new FormData(form) }, target, focusId, function () {
      form.submit(); // si algo falla, vuelve al envío normal
    });
  }

  root.addEventListener("submit", function (e) {
    var form = e.target.closest("form[data-enhance]");
    if (!form) return;
    e.preventDefault();
    send(form);
  });

  root.addEventListener("click", function (e) {
    var link = e.target.closest("a[data-enhance]");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    var href = link.href;
    request(href, { method: "GET" }, targetOf(link), link.dataset.fid, function () {
      window.location.href = href;
    }).then(function (ok) {
      if (ok && !link.getAttribute("data-target")) history.replaceState({}, "", href);
    });
  });

  root.addEventListener("change", function (e) {
    var select = e.target.closest("select[data-autosubmit]");
    if (select && select.form) select.form.requestSubmit();
  });

  // Vista previa en vivo: el formulario principal no se envía; se consulta la vista previa con sus valores.
  var live = document.querySelector("form[data-live-url]");
  if (live) {
    live.addEventListener("change", function () {
      var query = new URLSearchParams(new FormData(live));
      query.delete("csrfmiddlewaretoken");
      var target = document.querySelector(live.getAttribute("data-live-target") || "#preview");
      request(live.getAttribute("data-live-url") + "?" + query.toString(), { method: "GET" }, target, null, function () {});
    });
  }
})();
