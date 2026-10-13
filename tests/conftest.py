from pathlib import Path

import pytest
from django.test import Client

from apps.accounts import services
from apps.accounts.models import Person

PROXY_IP = "127.0.0.1"


def tailscale_client(login, name="", pic="", remote_addr=PROXY_IP):
    """Cliente que se comporta como `tailscale serve`: pone los encabezados de identidad."""
    extra = {"REMOTE_ADDR": remote_addr}
    if login:
        extra["HTTP_TAILSCALE_USER_LOGIN"] = login
    if name:
        extra["HTTP_TAILSCALE_USER_NAME"] = name
    if pic:
        extra["HTTP_TAILSCALE_USER_PROFILE_PIC"] = pic
    return Client(**extra)


@pytest.fixture
def make_person(db):
    def _make(login, status="approved", role="member"):
        person = Person.objects.create_user(login)
        services.set_role(person, role)
        person.status = status
        person.save(update_fields=["status"])
        return person

    return _make


@pytest.fixture
def member(make_person):
    return make_person("ana@example.com")


@pytest.fixture
def lead(make_person):
    return make_person("luis@example.com", role="lead")


@pytest.fixture
def admin_person(make_person):
    return make_person("jefe@example.com", role="admin")


@pytest.fixture
def client_for():
    return tailscale_client


@pytest.fixture
def member_client(member):
    return tailscale_client(member.login)


DGAC_FIXTURE = Path(__file__).parent / "fixtures" / "dgac"


@pytest.fixture
def site_world(db, settings, tmp_path, admin_person, member):
    """Sitio sembrado de punta a punta para la auditoría de enlaces.

    Catálogo, ruta DGAC de la fixture (nada de la ruta real), un hilo por categoría y una nota por ruta.
    """
    from django.core.management import call_command

    from apps.community import forum
    from apps.community import services as community
    from apps.community.models import Category, Note, Thread
    from apps.paths.models import LearningPath

    settings.MEDIA_ROOT = tmp_path
    settings.DGAC_DATA_DIR = DGAC_FIXTURE
    call_command("seed_catalog", verbosity=0)
    call_command("cargar_dgac", verbosity=0)
    for category in Category.objects.all():
        forum.create_thread(
            admin_person, category, Thread.Kind.DISCUSSION, f"Hilo {category.slug}", "hola"
        )
    for path in LearningPath.objects.all():
        community.create_note(member, path, "Nota de prueba", Note.Type.TIP)
    return {"admin": admin_person, "member": member}
