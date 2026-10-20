/* Lee el documento al elegirlo y rellena el formulario de credencial (mejora progresiva).
   El archivo viaja solo a este servidor (POST con CSRF); la lectura es local y no guarda nada.
   Solo rellena campos vacíos (o los que esta misma lectura rellenó antes y la persona no tocó). Sin JS, el formulario
   funciona igual: se escribe a mano. */
(function () {
  "use strict";
  var form = document.querySelector("form[data-read-url]");
  var input = document.getElementById("id_file");
  var status = document.getElementById("read-status");
  if (!form || !input || !status || !window.fetch || !window.FormData) return;

  var url = form.getAttribute("data-read-url");
  var editing = form.hasAttribute("data-editing");
  var TEXT = ["title", "issuer", "credential_id", "verify_url", "issued_on", "expires_on"];
  var SELECT = ["platform", "resource"];
  var runs = 0;

  function el(name) { return document.getElementById("id_" + name); }

  function chipHost(field) { return field.closest(".field"); }
  function dropChip(field) {
    var host = chipHost(field), chip = host && host.querySelector(".read-chip");
    if (chip) chip.remove();
  }
  function addChip(field) {
    var host = chipHost(field), label = host && host.querySelector("label");
    if (!label || host.querySelector(".read-chip")) return;
    var chip = document.createElement("span");
    chip.className = "chip cert read-chip";
    chip.textContent = "leído del documento";
    label.appendChild(chip);
  }

  function markTouched(e) {
    var t = e.target;
    if (!t || t === input || !t.dataset) return;
    t.dataset.touched = "1";
    if (t.dataset.fromDoc) { delete t.dataset.fromDoc; dropChip(t); }
  }
  form.addEventListener("input", markTouched);
  form.addEventListener("change", markTouched);

  function reset(field, name) {
    if (name === "skills") Array.prototype.forEach.call(field.options, function (o) { o.selected = false; });
    else if (name === "kind") field.value = "completion";
    else field.value = "";
    delete field.dataset.fromDoc;
    dropChip(field);
  }

  function available(field, name) {
    if (field.dataset.fromDoc) return true;
    if (name === "kind") return !editing && !field.dataset.touched && field.value === "completion";
    if (name === "skills") return !Array.prototype.some.call(field.options, function (o) { return o.selected; });
    return !field.value;
  }

  function apply(fields) {
    var filled = 0;
    // Limpia lo que una lectura anterior había puesto y la persona no tocó.
    TEXT.concat(SELECT, ["kind", "skills"]).forEach(function (name) {
      var f = el(name);
      if (f && f.dataset.fromDoc) reset(f, name);
    });
    TEXT.concat(SELECT, ["kind"]).forEach(function (name) {
      var f = el(name), v = fields[name];
      if (!f || v === undefined || v === null || v === "" || !available(f, name)) return;
      if (SELECT.indexOf(name) > -1 || name === "kind") {
        var ok = Array.prototype.some.call(f.options, function (o) { return o.value === String(v); });
        if (!ok) return;
      }
      f.value = String(v);
      f.dataset.fromDoc = "1";
      addChip(f);
      filled += 1;
    });
    var sk = el("skills");
    if (sk && fields.skills && fields.skills.length && available(sk, "skills")) {
      var ids = fields.skills.map(String), any = false;
      Array.prototype.forEach.call(sk.options, function (o) {
        if (ids.indexOf(o.value) > -1) { o.selected = true; any = true; }
      });
      if (any) { sk.dataset.fromDoc = "1"; addChip(sk); filled += 1; }
    }
    return filled;
  }

  function show(lines, warn) {
    status.textContent = "";
    status.classList.toggle("warn", !!warn);
    lines.forEach(function (text) {
      var p = document.createElement("span");
      p.textContent = text;
      status.appendChild(p);
    });
  }

  function csrf() {
    var t = form.querySelector("input[name=csrfmiddlewaretoken]");
    return t ? t.value : "";
  }

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    var run = ++runs;
    if (!file) { show([], false); return; }
    show(["Leyendo el documento…"], false);
    var body = new FormData();
    body.append("file", file);
    fetch(url, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" }
    })
      .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (run !== runs) return; // llegó otra lectura después
        if (data.error) { show([data.error], true); return; }
        if (data.unreadable || !data.ok) {
          show([data.message || "No pude leer este documento: completa a mano."], true);
          return;
        }
        var n = apply(data.fields || {});
        var lines = [];
        if (n > 0) lines.push("Leí el documento y rellené " + n + (n === 1 ? " campo" : " campos") + ": revísalos antes de guardar.");
        else lines.push("Leí el documento, pero no había campos vacíos que rellenar: revisa lo que ya escribiste.");
        (data.notes || []).forEach(function (w) { lines.push(w); });
        (data.warnings || []).forEach(function (w) { lines.push(w); });
        show(lines, (data.warnings || []).length > 0);
      })
      .catch(function () {
        if (run === runs) show(["No pude leer este documento: completa a mano."], true);
      });
  });
})();
