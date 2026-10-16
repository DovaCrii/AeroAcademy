"""Auditoría de enlaces: se recorre todo el sitio como admin, lead, miembro y pendiente siguiendo cada enlace interno.

Ningún enlace visible puede llevar a un 404 o a un 500. Una segunda prueba envía un POST por cada formulario distinto
(salvo los destructivos) y sigue la redirección conservando su `?query`. No mira URLs externas (eso lo hace
`manage.py revisar_enlaces --externos`).
"""

import re
from urllib.parse import urljoin, urlparse

import pytest

from apps.core.linkcheck import crawl, follow

pytestmark = pytest.mark.django_db
FORM = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.S | re.I)
ATTR = re.compile(r"""(\w[\w-]*)=["']([^"']*)["']""")
FIELD = re.compile(r"<(input|select|textarea)\b([^>]*)>", re.I)
DESTRUCTIVE = ("eliminar", "salir", "revocar", "rechazar", "retirar", "borrar", "/admin/")


@pytest.mark.parametrize("who", ["admin", "lead", "member", "pending"])
def test_no_internal_link_is_broken(site_world, client_for, make_person, who):
    person = {
        "admin": site_world["admin"],
        "member": site_world["member"],
        "lead": lambda: make_person("lider@example.com", role="lead"),
        "pending": lambda: make_person("pend@example.com", status="pending"),
    }[who]
    person = person() if callable(person) else person
    seen, broken, _ = crawl(client_for(person.login))
    if who != "pending":  # la persona pendiente solo ve /espera/
        assert len(seen) > 1000, f"El recorrido solo cubrió {len(seen)} URLs"
    assert not broken, "Enlaces rotos (código URL <- origen):\n" + "\n".join(broken)


@pytest.mark.parametrize("who", ["admin", "member"])
def test_post_forms_do_not_404(site_world, client_for, who):
    client = client_for(site_world[who].login)
    _, _, pages = crawl(client)
    forms = {}
    for url, html in sorted(pages.items()):
        for attrs, body in FORM.findall(html):
            attributes = dict(ATTR.findall(attrs))
            if attributes.get("method", "get").lower() != "post":
                continue
            action = urljoin(url, attributes.get("action", "") or url).replace("&amp;", "&")
            key = re.sub(r"\d+", "N", urlparse(action).path)
            if key in forms or any(word in action for word in DESTRUCTIVE):
                continue
            data = {}
            for _tag, raw in FIELD.findall(body):
                field = dict(ATTR.findall(raw))
                name = field.get("name")
                if not name or name == "csrfmiddlewaretoken" or name in data:
                    continue
                kind = field.get("type", "text")
                data[name] = field.get("value", "x" if kind in ("text", "search", "") else "1")
            forms[key] = (action, url, data)
    assert len(forms) > 20, f"Solo se encontraron {len(forms)} formularios distintos"
    failures = []
    for action, source, data in forms.values():
        response = client.post(action, data)
        status = response.status_code
        if status in (301, 302):
            _, final = follow(client, response["Location"])
            status = final.status_code if final is not None else 200
        # 400/403/405 son respuestas legítimas a datos inventados; un 404 o un 500 delatan un enlace o una vista rotos.
        if status == 404 or status >= 500:
            failures.append(f"{status} POST {action}  <- {source}")
    assert not failures, "Formularios rotos (código URL <- origen):\n" + "\n".join(failures)
