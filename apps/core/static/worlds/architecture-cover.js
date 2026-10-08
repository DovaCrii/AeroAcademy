/* Nube de puntos de la portada: un edificio y su terreno, coloreados por elevación. Respeta prefers-reduced-motion. */
(function () {
  "use strict";
  var cv = document.getElementById("cloudCv");
  if (!cv || !cv.getContext) return;
  var ctx = cv.getContext("2d");
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var pts = [];
  var seed = 7;
  function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }

  function box(x0, z0, w, d, h, n) {
    for (var i = 0; i < n; i++) {
      var face = Math.floor(rnd() * 5);
      var x = x0 + rnd() * w, z = z0 + rnd() * d, y = rnd() * h;
      if (face === 0) x = x0; else if (face === 1) x = x0 + w;
      else if (face === 2) z = z0; else if (face === 3) z = z0 + d; else y = h;
      pts.push([x, y, z, y / 18]);
    }
  }
  for (var i = 0; i < 900; i++) pts.push([rnd() * 60 - 30, rnd() * 0.6, rnd() * 40 - 20, 0]);
  box(-10, -6, 12, 10, 14, 700);
  box(4, -2, 9, 8, 9, 450);
  box(-22, 2, 8, 7, 5, 250);

  var angle = 0, W = 0, H = 0;
  function resize() {
    var dpr = window.devicePixelRatio || 1;
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function color(t) {
    t = Math.max(0, Math.min(1, t));
    var r = Math.round(30 + 225 * t), g = Math.round(140 + 60 * (1 - Math.abs(t - 0.5) * 2)), b = Math.round(255 - 215 * t);
    return "rgb(" + r + "," + g + "," + b + ")";
  }
  function draw() {
    ctx.clearRect(0, 0, W, H);
    var scale = Math.min(W, H * 1.6) / 52, cx = W * 0.72, cy = H * 0.8;
    var ca = Math.cos(angle), sa = Math.sin(angle);
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      var x = p[0] * ca - p[2] * sa, z = p[0] * sa + p[2] * ca;
      var sx = cx + x * scale, sy = cy - p[1] * scale * 1.1 + z * scale * 0.25;
      ctx.fillStyle = color(p[3]);
      ctx.globalAlpha = 0.55 + 0.4 * ((z + 30) / 60);
      ctx.fillRect(sx, sy, 2.2, 2.2);
    }
    ctx.globalAlpha = 1;
  }
  function frame() { angle += 0.0025; draw(); requestAnimationFrame(frame); }

  resize();
  window.addEventListener("resize", function () { resize(); draw(); });
  draw();
  if (!still) requestAnimationFrame(frame);
})();
