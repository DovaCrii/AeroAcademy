/* Nube de puntos del estilo "Levantamiento": puntos blancos y ámbar por elevación y una línea de escaneo.
   Uso: <canvas id="cloudCv" data-scene="building|terrain">. Respeta prefers-reduced-motion (imagen fija). */
(function () {
  "use strict";
  var cv = document.getElementById("cloudCv");
  if (!cv || !cv.getContext) return;
  var ctx = cv.getContext("2d");
  var scene = cv.getAttribute("data-scene") || "building";
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var pts = [];
  var seed = 11;
  function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }

  function box(x0, z0, w, d, h, n) {
    for (var i = 0; i < n; i++) {
      var face = Math.floor(rnd() * 5);
      var x = x0 + rnd() * w, z = z0 + rnd() * d, y = rnd() * h;
      if (face === 0) x = x0; else if (face === 1) x = x0 + w;
      else if (face === 2) z = z0; else if (face === 3) z = z0 + d; else y = h;
      pts.push([x, y, z, Math.min(1, y / 16)]);
    }
  }
  function ground(n, spread) {
    for (var i = 0; i < n; i++) pts.push([rnd() * spread - spread / 2, rnd() * 0.5, rnd() * 44 - 22, 0]);
  }
  function terrain(n) {
    for (var i = 0; i < n; i++) {
      var x = rnd() * 70 - 35, z = rnd() * 50 - 25;
      var y = 5 + 3.5 * Math.sin(x * 0.22) + 3 * Math.cos(z * 0.3) + 1.6 * Math.sin((x + z) * 0.5);
      pts.push([x, y, z, Math.min(1, Math.max(0, (y - 1) / 11))]);
    }
  }
  if (scene === "terrain") { terrain(2600); }
  else { ground(1100, 64); box(-10, -6, 12, 10, 14, 800); box(4, -2, 9, 8, 9, 500); box(-22, 2, 8, 7, 5, 280); }

  var angle = 0, scan = 0.2, W = 0, H = 0;
  function resize() {
    var dpr = window.devicePixelRatio || 1;
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function tone(t, hot) {
    if (hot) return "rgb(255," + Math.round(190 + 50 * t) + ",90)";
    if (t < 0.34) return "rgb(" + Math.round(190 + 50 * t) + "," + Math.round(205 + 40 * t) + ",255)";
    if (t < 0.7) return "rgb(120,160," + Math.round(255 - 60 * t) + ")";
    return "rgb(244," + Math.round(166 + 60 * (t - 0.7)) + ",42)";
  }
  function draw() {
    ctx.clearRect(0, 0, W, H);
    var s = Math.min(W, H * 1.6) / 52, cx = W * 0.72, cy = H * 0.8;
    var ca = Math.cos(angle), sa = Math.sin(angle), band = H * 0.05, lineY = scan * H;
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      var x = p[0] * ca - p[2] * sa, z = p[0] * sa + p[2] * ca;
      var sx = cx + x * s, sy = cy - p[1] * s * 1.1 + z * s * 0.25;
      var hot = Math.abs(sy - lineY) < band;
      ctx.fillStyle = tone(p[3], hot);
      ctx.globalAlpha = hot ? 0.95 : 0.5 + 0.4 * ((z + 30) / 60);
      var size = hot ? 2.6 : 2;
      ctx.fillRect(sx, sy, size, size);
    }
    ctx.globalAlpha = 1;
    var g = ctx.createLinearGradient(0, lineY - 14, 0, lineY + 14);
    g.addColorStop(0, "rgba(244,166,42,0)");
    g.addColorStop(0.5, "rgba(244,166,42,.9)");
    g.addColorStop(1, "rgba(244,166,42,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, lineY - 14, W, 28);
  }
  function frame() {
    angle += 0.0022;
    scan += 0.0016;
    if (scan > 1.08) scan = -0.08;
    draw();
    requestAnimationFrame(frame);
  }

  resize();
  window.addEventListener("resize", function () { resize(); draw(); });
  scan = still ? 0.62 : 0.1;
  draw();
  if (!still) requestAnimationFrame(frame);
})();
