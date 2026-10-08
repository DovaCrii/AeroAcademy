/* Mejora progresiva (equivalente local de HTMX): formularios y enlaces con `data-enhance` actualizan
   solo la región `#path-app`, sin recargar. Sin JS, todo funciona con formularios y enlaces normales. */
(function () {
  "use strict";
  var root = document.querySelector("[data-enhance-root]");
  if (!root || !window.fetch) return;

  function focusAgain(id) {
    if (!id) return;
    var el = root.querySelector('[data-fid="' + id + '"]');
    if (el) el.focus({ preventScroll: true });
  }

  function swap(html, focusId) {
    root.innerHTML = html;
    focusAgain(focusId);
  }

  function request(url, options, focusId, fallback) {
    options.headers = { "X-Partial": "1", "X-Requested-With": "fetch" };
    options.credentials = "same-origin";
    return fetch(url, options)
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        return r.text();
      })
      .then(function (html) { swap(html, focusId); return true; })
      .catch(function () { fallback(); });
  }

  root.addEventListener("submit", function (e) {
    var form = e.target.closest("form[data-enhance]");
    if (!form) return;
    e.preventDefault();
    var active = document.activeElement;
    var focusId = active && active.dataset ? active.dataset.fid : null;
    request(form.action, { method: "POST", body: new FormData(form) }, focusId, function () {
      form.submit(); // si algo falla, vuelve al envío normal
    });
  });

  root.addEventListener("click", function (e) {
    var link = e.target.closest("a[data-enhance]");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    var href = link.href;
    request(href, { method: "GET" }, link.dataset.fid, function () {
      window.location.href = href;
    }).then(function (ok) {
      if (ok) history.replaceState({}, "", href);
    });
  });

  root.addEventListener("change", function (e) {
    var select = e.target.closest("select[data-autosubmit]");
    if (select && select.form) select.form.requestSubmit();
  });
})();
