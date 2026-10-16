"""Revisión de enlaces: recorrido interno con un cliente de Django y comprobación de URLs externas.

La usan `manage.py revisar_enlaces` y `tests/test_enlaces.py`. Solo mira la ruta y el código de cada URL: no guarda
contenido de páginas ni datos de personas.
"""

import re
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

LINK = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
SKIP = (
    "/static/",
    "/media/",
    "/admin/",
    "/descargar",
    "/descarga",
    "/exportar",
    "/export",
    "/salir",
)
LOCAL_HOSTS = ("", "testserver", "localhost")
LIMIT = 3000
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)\]]+")


def internal(url, href):
    """URL interna (con `?query`) a la que apunta `href`, o None si sale del sitio o no se sigue."""
    href = urldefrag(href.replace("&amp;", "&"))[0]
    parsed = urlparse(href)
    if (
        parsed.scheme
        or parsed.netloc
        or not href
        or href.startswith(("mailto:", "tel:", "javascript:"))
    ):
        return None
    target = urljoin(url, href)
    if any(s in target for s in SKIP):
        return None
    p = urlparse(target)
    # El catálogo combina filtros sin fin: se sigue como máximo un filtro y nunca la paginación.
    if p.path == "/catalogo/" and (p.query.count("&") >= 1 or "page=" in p.query):
        return None
    return target


def follow(client, url):
    """GET con la redirección resuelta (se conserva la query). Devuelve (url final, respuesta o None)."""
    response = client.get(url)
    for _ in range(5):
        if response.status_code not in (301, 302):
            break
        target = urlparse(urljoin(url, response["Location"]))
        if target.netloc not in LOCAL_HOSTS:
            return url, None
        url = target.path + (f"?{target.query}" if target.query else "")
        response = client.get(url)
    return url, response


def crawl(client, start="/", limit=LIMIT):
    """Recorre el sitio desde `start`. Devuelve (URLs vistas, rotas como «código URL <- origen», html por URL)."""
    seen, broken, pages = set(), [], {}
    queue = deque([(start, "(inicio)")])
    while queue and len(seen) < limit:
        url, origin = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        final, response = follow(client, url)
        if response is None:
            continue
        seen.add(final)
        if response.status_code >= 400:
            broken.append(f"{response.status_code} {url}  <- {origin}")
            continue
        if "text/html" not in response.get("Content-Type", ""):
            continue
        html = response.content.decode()
        pages[final] = html
        for href in LINK.findall(html):
            target = internal(final, href)
            if target and target not in seen:
                queue.append((target, final))
    return seen, broken, pages


# ---- externos -------------------------------------------------------------------------------------------------


def seed_urls(seed_dir):
    """Todas las URLs http(s) de `seed/` → {url: archivo donde aparece}."""
    found = {}
    for path in sorted(Path(seed_dir).rglob("*.json")):
        for url in URL_IN_TEXT.findall(path.read_text(encoding="utf-8")):
            found.setdefault(url.rstrip(".,;"), path.name)
    return found


def resource_urls():
    from apps.catalog.models import Resource

    return {
        url: f"Recurso: {title}"
        for url, title in Resource.objects.exclude(url="").values_list("url", "title")
    }


def classify(status):
    """Separa los 404 reales de los bloqueos antibot y de los fallos pasajeros."""
    if status in (404, 410):
        return "roto"
    if status in (401, 403, 429, 999):
        return "bloqueado"
    if isinstance(status, int) and 200 <= status < 400:
        return "ok"
    if isinstance(status, int) and status >= 500:
        return "error_servidor"
    return "sin_respuesta"


def check_url(url, timeout=15):
    """Devuelve el código HTTP (HEAD y, si no sirve, GET) o el texto del fallo (timeout, DNS…)."""
    last = None
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": BROWSER_UA})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (solo http/https)
                return response.status
        except urllib.error.HTTPError as exc:
            last = exc.code
            if method == "HEAD" and exc.code in (403, 404, 405, 429, 500, 501):
                continue  # algunos sitios no aceptan HEAD: se confirma con GET
            return exc.code
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = type(exc).__name__
            if method == "HEAD":
                continue
    return last


def check_external(urls, workers=8, checker=None):
    """urls: {url: origen}. Devuelve filas [url, origen, código, clase] ordenadas por clase y URL."""
    checker = checker or check_url
    urls = {u: o for u, o in urls.items() if urlparse(u).scheme in ("http", "https")}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        codes = list(pool.map(checker, urls))
    rows = [[u, urls[u], code, classify(code)] for u, code in zip(urls, codes, strict=True)]
    rows.sort(key=lambda r: (r[3], r[0]))
    return rows
