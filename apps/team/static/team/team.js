// Botones «Copiar»: copian el texto de la caja indicada en data-copy (sin JS, la caja se puede seleccionar a mano).
document.addEventListener("click", function (e) {
  var btn = e.target.closest("[data-copy]");
  if (!btn) return;
  var box = document.getElementById(btn.getAttribute("data-copy"));
  if (!box) return;
  var done = function () {
    var old = btn.textContent;
    btn.textContent = "Copiado";
    setTimeout(function () { btn.textContent = old; }, 1500);
  };
  box.select();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(box.value).then(done, function () { document.execCommand("copy"); done(); });
  } else {
    document.execCommand("copy");
    done();
  }
});
