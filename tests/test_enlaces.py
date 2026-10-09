"""Auditoría de enlaces: se recorre el sitio como administradora y como miembro siguiendo cada enlace interno.

Ningún enlace visible puede llevar a un 404 o a un error 500 (las descargas y los POST no se siguen).
"""

import re
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db
HREF = re.compile(r'href="([^"]+)"')
SKIP = ("/static/", "/media/", "/admin/", "/descargar", "/descarga", "/exportar", "/export")
LIMIT = 400


@pytest.fixture
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_catalog", verbosity=0)


def crawl(client, start="/"):
    seen, broken = set(), []
    queue = deque([(start, "(inicio)")])
    while queue and len(seen) < LIMIT:
        url, origin = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        response = client.get(url)
        if response.status_code in (301, 302):
            target = urljoin(url, response["Location"])
            if urlparse(target).netloc in ("", "testserver"):
                queue.append((urlparse(target).path or "/", url))
            continue
        if response.status_code >= 400:
            broken.append(f"{response.status_code} {url}  (enlazado desde {origin})")
            continue
        if "text/html" not in response.get("Content-Type", ""):
            continue
        for href in HREF.findall(response.content.decode()):
            href = urldefrag(href.replace("&amp;", "&"))[0]
            parsed = urlparse(href)
            if (
                parsed.scheme
                or parsed.netloc
                or not href
                or href.startswith(("mailto:", "tel:", "javascript:"))
            ):
                continue
            target = urljoin(url, href)
            if target.startswith(SKIP) or any(s in target for s in SKIP):
                continue
            if target not in seen:
                queue.append((target, url))
    return seen, broken


@pytest.mark.parametrize("who", ["admin_person", "member"])
def test_no_internal_link_is_broken(seeded, client_for, request, who):
    person = request.getfixturevalue(who)
    seen, broken = crawl(client_for(person.login))
    assert len(seen) > 20
    assert not broken, "Enlaces rotos:\n" + "\n".join(broken)
