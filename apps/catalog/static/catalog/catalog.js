/* Carruseles del catálogo: funcionan sin JS (scroll-snap); aquí solo se agregan flechas y el indicador «1/4». */
(function () {
  "use strict";
  document.querySelectorAll("[data-rail]").forEach(function (wrap) {
    var rail = wrap.querySelector(".cat-rail");
    if (!rail) return;
    var ctl = document.createElement("div");
    ctl.className = "cat-ctl";
    ctl.innerHTML =
      '<button type="button" aria-label="Anteriores">‹</button><output aria-live="polite"></output>' +
      '<button type="button" aria-label="Siguientes">›</button>';
    var prev = ctl.children[0], out = ctl.children[1], next = ctl.children[2];
    wrap.parentNode.querySelector(".cat-row-h").after(ctl);

    function pages() { return Math.max(1, Math.ceil(rail.scrollWidth / rail.clientWidth - 0.05)); }
    function update() {
      var n = pages();
      var i = Math.min(n, Math.round(rail.scrollLeft / Math.max(1, rail.clientWidth)) + 1);
      if (rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 4) i = n;
      out.textContent = i + "/" + n;
      prev.disabled = rail.scrollLeft <= 2;
      next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 4;
      ctl.hidden = n <= 1;
    }
    function go(dir) {
      var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      rail.scrollBy({ left: dir * rail.clientWidth * 0.9, behavior: still ? "auto" : "smooth" });
    }
    prev.addEventListener("click", function () { go(-1); });
    next.addEventListener("click", function () { go(1); });
    rail.addEventListener("scroll", function () { window.requestAnimationFrame(update); }, { passive: true });
    window.addEventListener("resize", update);
    update();
  });
})();
