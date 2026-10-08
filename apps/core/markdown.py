"""Markdown mínimo y **seguro** para artículos (sin dependencias).

Primero se escapa todo el texto (`<` → `&lt;`…), después se agregan solo estas etiquetas: títulos, párrafos, listas,
citas, bloques y trozos de código, negrita y enlaces. Un enlace solo puede ser `https://…`, `http://…` o una ruta
local `/…`; nada de `javascript:`, `data:` ni imágenes. El HTML que el usuario escriba sale como texto.
"""

import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_HEADING = re.compile(r"^(#{1,3})\s+(.+)$")
_UL = re.compile(r"^[-*]\s+(.+)$")
_OL = re.compile(r"^\d+[.)]\s+(.+)$")
_SAFE_URL = re.compile(r"^(https?://[^\s\"'<>]+|/(?!/)[^\s\"'<>]*)$")


def _link(match):
    label, url = match.group(1), match.group(2)
    raw = url.replace("&amp;", "&")
    if not _SAFE_URL.match(raw):
        return match.group(0)  # no es un enlace permitido: queda como texto
    external = raw.startswith("http")
    extra = ' rel="noopener noreferrer" target="_blank"' if external else ""
    return f'<a href="{url}"{extra}>{label}</a>'


def _inline(text):
    parts = _CODE.split(text)  # los trozos impares son código: no se les aplica formato
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f"<code>{part}</code>")
        else:
            part = _LINK.sub(_link, part)
            part = _BOLD.sub(r"<strong>\1</strong>", part)
            out.append(part)
    return "".join(out)


def render(text):
    """Devuelve HTML seguro (SafeString) a partir de Markdown mínimo."""
    lines = escape(text or "").replace("\r\n", "\n").split("\n")
    html, para, items, kind, quote, code = [], [], [], None, [], None

    def flush():
        nonlocal para, items, kind, quote
        if para:
            html.append("<p>" + _inline(" ".join(para)) + "</p>")
        if items:
            html.append(
                f"<{kind}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{kind}>"
            )
        if quote:
            html.append("<blockquote>" + _inline(" ".join(quote)) + "</blockquote>")
        para, items, kind, quote = [], [], None, []

    for line in lines:
        if code is not None:
            if line.strip().startswith("```"):
                html.append("<pre><code>" + "\n".join(code) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            code = []
            continue
        if not stripped:
            flush()
            continue
        if m := _HEADING.match(stripped):
            flush()
            level = len(m.group(1)) + 1  # el h1 es el de la página
            html.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif m := _UL.match(stripped):
            if kind not in (None, "ul") or para or quote:
                flush()
            kind = "ul"
            items.append(m.group(1))
        elif m := _OL.match(stripped):
            if kind not in (None, "ol") or para or quote:
                flush()
            kind = "ol"
            items.append(m.group(1))
        elif stripped.startswith("&gt;"):
            if items or para:
                flush()
            quote.append(stripped[4:].strip())
        else:
            if items or quote:
                flush()
            para.append(stripped)
    if code is not None:  # bloque sin cerrar
        html.append("<pre><code>" + "\n".join(code) + "</code></pre>")
    flush()
    return mark_safe("".join(html))  # noqa: S308  (todo el texto fue escapado antes)
