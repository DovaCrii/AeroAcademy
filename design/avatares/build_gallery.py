"""Genera design/avatares/galeria.html con el motor real (apps/gamification/avatar).

Uso (desde la raíz del repositorio):  python design/avatares/build_gallery.py
No necesita Django: el motor solo usa la biblioteca estándar.
"""

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.gamification import avatar as av  # noqa: E402
from apps.gamification.avatar import engine  # noqa: E402

CAT = av.catalog()
BASE = {"class": "architect", "body": "neutral", "skin": 2, "hair": "short", "hair_color": 2, "eyes": "iris",
        "eye_color": 1, "mouth": "smile", "outfit": "tshirt", "outfit_color": 0, "headwear": "none"}  # fmt: skip
NAMES = ["Ana Muñoz", "Luis Gómez", "Camila Rojas", "Diego Soto", "Paula Vera", "Tomás Díaz", "Sofía Lagos",
         "Matías Pino", "Valentina Cruz", "Joaquín Mena", "Isidora Páez", "Felipe Araya", "Rocío Bravo",
         "Nicolás Tapia", "Antonia Reyes", "Benjamín Ortiz", "Javiera Mora", "Cristóbal Vega"]  # fmt: skip


def svg(cfg, size, label="Avatar", view="full", frame=True):
    body = av.render_svg(cfg, title=label, view=view, frame=frame)
    return body.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


def card(cfg, size, title, sub=""):
    return (
        f'<figure class="c" style="--w:{size + 16}px"><div class="px">{svg(cfg, size, title)}</div>'
        f"<figcaption><b>{escape(title)}</b><span>{escape(sub)}</span></figcaption></figure>"
    )


def options(category, size=96, base=None, view="full", frame=False):
    base = {**BASE, **(base or {})}
    out = []
    for opt in CAT[category]:
        cfg = {**base, category: opt["id"]}
        locked = engine.UNLOCKS.get(category, {}).get(opt["id"])
        sub = f"🔒 {locked}" if locked else ""
        out.append(
            f'<figure class="c" style="--w:{size + 16}px"><div class="px">{svg(cfg, size, opt["label"], view, frame)}</div>'
            f"<figcaption><b>{escape(opt['label'])}</b><span>{escape(sub)}</span></figcaption></figure>"
        )
    return "".join(out)


def swatches(category, size=64, base=None):
    base = {**BASE, **(base or {})}
    return "".join(
        f'<figure class="c" style="--w:{size + 12}px"><div class="px">{svg({**base, category: o["id"]}, size, o["label"], "bust", False)}</div>'
        f'<figcaption><b>{escape(o["label"])}</b></figcaption></figure>'
        for o in CAT[category]
    )


def section(n, title, body, note=""):
    extra = f'<p class="cap" style="margin-top:10px">{note}</p>' if note else ""
    return f'<h2>// {n:02d} · {escape(title)}</h2><div class="grid">{body}</div>{extra}'


def build():
    hair_base = {"hair_color": 1}
    parts = [
        section(1, "Tres cuerpos, la misma cara", options("body", 128, {"hair": "side_part"}),
                "Hombre, mujer o neutro: cambian los hombros y el mentón; el resto se combina como quieras."),
        section(2, "Cinco clases", "".join(
            card({**BASE, "class": c, "hair": h, "hair_color": hc, "skin": s, "outfit": engine.CLASS_DEFAULTS[c]["outfit"],
                  "outfit_color": engine.CLASS_DEFAULTS[c]["outfit_color"], "background": engine.CLASS_DEFAULTS[c]["background"]},
                 128, engine.CLASS_LABELS[c])
            for c, h, hc, s in [("architect", "side_part", 1, 1), ("engineer", "ponytail", 3, 4), ("cartographer", "curly", 0, 5),
                                ("artificer", "buzz", 7, 2), ("pilot", "long", 9, 0)]
        ), "La ropa de partida cambia con la clase, pero todo se puede editar."),
        section(3, "Peinados", options("hair", 96, hair_base), "14 peinados, con 12 colores (incluidos fantasía)."),
        section(4, "Barba y bigote", options("facial_hair", 96, {"hair": "short", "body": "masculine", "hair_color": 2})),
        section(5, "Lentes", options("glasses", 96)),
        section(6, "Gorros y sombreros", options("headwear", 96, {"hair": "wavy", "hair_color": 3})),
        section(7, "Ropa", options("outfit", 96, {"hair": "short"})),
        section(8, "Accesorio de cuello", options("neckwear", 96, {"outfit": "shirt_tie"})),
        section(9, "Parte de abajo", options("legwear", 96)),
        section(10, "Ojos", options("eyes", 96, {"hair": "bob"}) + "", ""),
        section(11, "Cejas", options("brows", 96)),
        section(12, "Boca", options("mouth", 96)),
        section(13, "Tono de piel", swatches("skin", 80)),
        section(14, "Color de pelo", swatches("hair_color", 80, {"hair": "wavy"})),
        section(15, "Color de ojos", swatches("eye_color", 80, {"eyes": "iris"})),
        section(16, "Color de la ropa", swatches("outfit_color", 80, {"outfit": "hoodie"})),
    ]
    team = "".join(
        card({**av.default_config(f"{n.lower().replace(' ', '.')}@lev.cl"), "frame": ["common", "common", "rare", "epic"][i % 4]},
             96, n, "avatar inicial automático")
        for i, n in enumerate(NAMES)
    )  # fmt: skip
    frames = "".join(
        card({**BASE, "hair": "curly", "hair_color": 4, "headwear": "none", "glasses": "round", "frame": f}, 96,
             {"common": "Común", "rare": "Rara", "epic": "Épica", "legendary": "Legendaria"}[f], "marco por rareza")
        for f in engine.palettes.FRAMES
    )  # fmt: skip
    me = {**BASE, "class": "engineer", "hair": "ponytail", "hair_color": 3, "headwear": "cap", "glasses": "round", "eyes": "lashes",
          "body": "feminine", "outfit": "hivis_vest", "outfit_color": 1, "frame": "rare", "skin": 4}  # fmt: skip
    sizes = "".join(
        f'<div class="sz"><div class="px">{svg(me, s, "Ejemplo", "full")}</div><span>{s}px</span></div>' for s in (32, 64, 96, 128, 192)
    )
    busts = "".join(
        f'<div class="sz"><div class="px">{svg(me, s, "Ejemplo", "bust")}</div><span>busto {s}px</span></div>' for s in (24, 32, 48)
    )
    rows = "".join(
        f'<tr><td><span class="px">{svg(av.default_config(f"{n.lower().replace(" ", ".")}@lev.cl"), 40, n, "bust")}</span></td>'
        f"<td><b>{escape(n)}</b><br><small>{['Arquitecto-Constructor', 'Calculista', 'Cartógrafo', 'Piloto de Nubes'][i % 4]}</small></td>"
        f'<td><span class="lv">NV {4 + i * 2}</span></td><td><small>{["Aprendiz de Cota", "Guardián del Eje", "Portador del Jalón", "Domador de Hélices"][i % 4]}</small></td></tr>'
        for i, n in enumerate(NAMES[:5])
    )  # fmt: skip

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Galería de avatares pixel-art</title>
<style>
:root{{--bg:#0A0E1A;--panel:#0F1830;--line:rgba(170,195,255,.3);--ink:#EAF0FF;--dim:#8FA3C8;--amber:#F4A62A;
--rarity-common:#8D9CAD;--rarity-rare:#1E8CFF;--rarity-epic:#8B5CF6;--rarity-legendary:#E0A800;
--serif:"Iowan Old Style","Palatino Linotype",Georgia,serif;--mono:ui-monospace,Consolas,monospace;--font:"Archivo",Arial,sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.5}}
.wrap{{max-width:1240px;margin:0 auto;padding:0 18px 60px}}
header{{padding:44px 0 10px;border-bottom:1px solid var(--line);margin-bottom:8px}}
.cap{{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}}
h1{{font-family:var(--serif);font-style:italic;color:var(--amber);font-size:clamp(34px,5vw,56px);margin:6px 0}}
h2{{font-family:var(--mono);font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--amber);margin:40px 0 14px;font-weight:600}}
p.l{{color:#D5E0F7;max-width:72ch;margin:0}}
.grid{{display:flex;flex-wrap:wrap;gap:14px}}
.c{{margin:0;width:var(--w,140px);text-align:center}}
.c figcaption b{{display:block;font-size:13px;margin-top:6px;line-height:1.2}}.c figcaption span{{font-family:var(--mono);font-size:10.5px;color:var(--dim);display:block}}
.px svg{{display:block;image-rendering:pixelated;margin:0 auto}}.px{{display:inline-block}}
.c .px{{padding:6px;background:var(--panel);border:1px solid var(--line)}}
.sizes{{display:flex;align-items:flex-end;gap:22px;flex-wrap:wrap;margin-bottom:12px}}.sz{{text-align:center;font-family:var(--mono);font-size:11px;color:var(--dim)}}
.card{{background:var(--panel);border:1px solid var(--line);padding:16px 18px;min-width:0}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td{{padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:middle}}
.lv{{font-family:var(--mono);color:#0A0E1A;font-weight:700;background:var(--amber);padding:2px 6px;display:inline-block;white-space:nowrap}}
small{{color:var(--dim)}}
.chip{{display:inline-flex;align-items:center;gap:10px;background:#0A0E13;border:1px solid var(--line);padding:6px 12px}}
.post{{display:grid;grid-template-columns:auto 1fr;gap:12px}}.post p{{margin:2px 0 0;color:#D5E0F7}}
.bubble{{border:3px solid #fff;background:#0A0E13;padding:8px 10px;font-size:13px;margin-top:8px}}
.floor{{display:flex;align-items:center;gap:6px;border:1px solid var(--line);padding:6px 10px;margin-bottom:6px;font-family:var(--mono);font-size:12px}}
.floor b{{color:var(--amber)}}.floor .px{{margin-left:auto;display:flex;gap:2px}}
.rule li{{margin-bottom:6px}}
@media(prefers-reduced-motion:no-preference){{.c:hover .px svg{{transform:translateY(-3px);transition:transform .15s steps(2)}}}}
</style></head><body><div class="wrap">
<header><span class="cap">AeroAcademy · Academia LEV Digital 101 · hoja de personaje</span>
<h1>Figuritas del equipo</h1>
<p class="l">Cada persona arma su avatar pixel-art de <b>32×32</b>: cuerpo, piel, cara, pelo, barba, lentes, gorro, ropa, colores, fondo y un marco de rareza. Se genera con el motor de <code>apps/gamification/avatar</code> (sin dependencias) y se edita en <code>/perfil/avatar/</code>. Esta galería sale del mismo código.</p></header>
{"".join(parts)}
<h2>// 17 · El equipo (avatar inicial automático desde el login)</h2><div class="grid">{team}</div>
<h2>// 18 · Marcos por rareza</h2><div class="grid">{frames}</div>
<h2>// 19 · Una misma figurita a todos los tamaños</h2>
<div class="sizes">{sizes}</div><div class="sizes">{busts}</div>
<p class="cap">El avatar completo se ve en múltiplos de 32 (32, 64, 96…); el <b>busto</b> (cabeza y hombros) es para tamaños chicos como la cabecera.</p>
<h2>// 20 · Dónde se ve</h2>
<div class="two">
  <div class="card"><span class="cap">Cabecera</span><br><br>
    <span class="chip"><span class="px">{svg(me, 32, "Tu avatar", "bust")}</span><span><b>Ana Muñoz</b><br><small>NV 6 · Guardián del Eje</small></span></span></div>
  <div class="card"><span class="cap">Foro · respuesta aceptada</span><br><br>
    <div class="post"><span class="px">{svg({**me, "body": "masculine", "headwear": "none", "facial_hair": "beard", "hair": "quiff", "hair_color": 1, "class": "pilot", "outfit": "flight_jacket", "outfit_color": 4}, 56, "Diego", "bust")}</span>
    <div><b>Diego Soto</b> <small>· Domador de Hélices · NV 9</small><p>Con <em>Insert → Point Cloud</em> el .rcp entra georreferenciado.</p></div></div></div>
  <div class="card" style="grid-column:1/-1"><span class="cap">Equipo · tabla de avance</span><br><br><table>{rows}</table></div>
  <div class="card"><span class="cap">Corte del edificio · quién está en cada piso</span><br><br>
    <div class="floor"><b>N3</b> Forma ↔ Revit<span class="px">{svg(av.default_config("ana@lev.cl"), 28, "Ana", "bust", False)}{svg(av.default_config("luis@lev.cl"), 28, "Luis", "bust", False)}</span></div>
    <div class="floor"><b>N2</b> Site Design<span class="px">{svg(me, 28, "Yo", "bust", False)}</span></div>
    <div class="floor"><b>N1</b> Fundamentos Revit<span class="px"></span></div></div>
  <div class="card"><span class="cap">Subida de nivel</span><br><br>
    <div style="display:flex;gap:14px;align-items:center"><span class="px">{svg({**me, "frame": "epic"}, 96, "Nivel nuevo")}</span>
    <div><div class="cap">Nivel 7</div><b style="font-family:var(--serif);font-style:italic;color:var(--amber);font-size:24px">Topógrafo Arcano</b>
    <div class="bubble">¡Buena medición! Desbloqueaste el marco <b>épico</b>.</div></div></div></div>
</div>
<h2>// 21 · Reglas para que se vea claro</h2>
<ul class="rule">
<li><b>Contorno oscuro de 1 px</b> en todas las piezas: se lee sobre cualquier fondo, claro u oscuro.</li>
<li><b>Máximo 3 tonos por zona</b> (base, luz, sombra) y una paleta común para toda la familia.</li>
<li><b>La clase se reconoce por el color y el tipo de ropa</b> (corbata, chaleco reflectante, chaleco de campo, delantal, chaqueta de vuelo).</li>
<li><b>El marco dice la rareza</b> con color; los accesorios que se desbloquean muestran su candado y la insignia que los abre.</li>
<li><b>Busto en los tamaños chicos</b> (24 a 48 px) y figura completa desde 64 px; siempre múltiplos enteros.</li>
<li><b>Nada parpadea</b>: la única animación es un salto de 3 px al pasar el cursor, apagado con <i>reduced motion</i>.</li>
</ul>
</div></body></html>
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(__file__).with_name("galeria.html")
    out.write_text(build(), encoding="utf-8")
    print("escrito", out, out.stat().st_size, "bytes")
