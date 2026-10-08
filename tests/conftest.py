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
    return make_person("ana@lev.cl")


@pytest.fixture
def lead(make_person):
    return make_person("luis@lev.cl", role="lead")


@pytest.fixture
def admin_person(make_person):
    return make_person("jefe@lev.cl", role="admin")


@pytest.fixture
def client_for():
    return tailscale_client


@pytest.fixture
def member_client(member):
    return tailscale_client(member.login)
