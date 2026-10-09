/* Prueba RPAS: una tarjeta por pregunta, con avance tipo altímetro y teclado.
   Sin JS, el formulario muestra las preguntas una bajo otra y funciona igual. */
(function () {
  "use strict";
  var form = document.querySelector("[data-dgac-quiz]");
  if (!form) return;
  var cards = Array.prototype.slice.call(form.querySelectorAll(".dg-q"));
  if (!cards.length) return;
  var dots = Array.prototype.slice.call(form.querySelectorAll("[data-dot]"));
  var cur = 0;
  var prev = form.querySelector("[data-prev]");
  var next = form.querySelector("[data-next]");
  var warn = form.querySelector("[data-warn]");
  var hudCur = form.querySelector("[data-hud-current]");
  var hudDone = form.querySelector("[data-hud-done]");
  var hudBar = form.querySelector("[data-hud-bar]");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  form.classList.add("is-wizard");
  prev.hidden = false;
  next.hidden = false;

  function answered(card) { return !!card.querySelector("input:checked"); }
  function countDone() { return cards.filter(answered).length; }

  function render() {
    cards.forEach(function (c, i) { c.classList.toggle("is-current", i === cur); });
    dots.forEach(function (d, i) {
      d.classList.toggle("cur", i === cur);
      d.classList.toggle("on", answered(cards[i]));
    });
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    hudCur.textContent = pad(cur + 1);
    var done = countDone();
    hudDone.textContent = done;
    hudBar.style.width = Math.round(100 * done / cards.length) + "%";
    prev.disabled = cur === 0;
    form.classList.toggle("at-end", cur === cards.length - 1);
  }

  function go(i, focus) {
    cur = Math.max(0, Math.min(cards.length - 1, i));
    render();
    if (focus !== false) {
      var target = cards[cur].querySelector("input:checked") || cards[cur].querySelector("input");
      if (target) target.focus({ preventScroll: true });
      var top = form.getBoundingClientRect().top + window.scrollY - 110;
      window.scrollTo({ top: Math.max(0, top), behavior: reduce ? "auto" : "smooth" });
    }
  }

  prev.addEventListener("click", function () { go(cur - 1); });
  next.addEventListener("click", function () { go(cur + 1); });
  dots.forEach(function (d, i) { d.addEventListener("click", function () { go(i); }); });

  form.addEventListener("change", function () {
    render();
    warn.hidden = true;
  });

  form.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var key = e.key;
    var inputs = cards[cur].querySelectorAll("input[type=radio]");
    var idx = -1;
    if (/^[1-9]$/.test(key)) idx = parseInt(key, 10) - 1;
    else if (/^[a-dA-D]$/.test(key)) idx = key.toLowerCase().charCodeAt(0) - 97;
    if (idx >= 0 && idx < inputs.length) {
      inputs[idx].checked = true;
      inputs[idx].dispatchEvent(new Event("change", { bubbles: true }));
      e.preventDefault();
      return;
    }
    if (key === "ArrowRight" && e.target.type !== "radio") { go(cur + 1); e.preventDefault(); }
    if (key === "ArrowLeft" && e.target.type !== "radio") { go(cur - 1); e.preventDefault(); }
    if (key === "Enter" && e.target.type === "radio") {
      if (cur < cards.length - 1) go(cur + 1);
      e.preventDefault();
    }
  });
  form.addEventListener("submit", function (e) {
    var left = cards.length - countDone();
    if (left > 0 && !form.dataset.confirmed) {
      e.preventDefault();
      form.dataset.confirmed = "1";
      warn.hidden = false;
      warn.textContent = "Te faltan " + left + " pregunta" + (left === 1 ? "" : "s") + " por responder y cuentan como incorrectas. Pulsa «Entregar la prueba» otra vez para enviar igual.";
    }
  });

  render();
})();
