"""«Salir» solo se ofrece a quien entró con contraseña: con Tailscale la siguiente visita vuelve a entrar sola."""

import pytest

pytestmark = pytest.mark.django_db
LOGOUT = ">Salir</button>"


def test_tailscale_session_does_not_show_logout(client_for, member):
    assert LOGOUT not in client_for(member.login).get("/").content.decode()


def test_password_session_shows_logout(client, member):
    member.set_password("una-clave-de-prueba-larga")
    member.save()
    client.force_login(member, backend="django.contrib.auth.backends.ModelBackend")
    assert LOGOUT in client.get("/", REMOTE_ADDR="127.0.0.1").content.decode()
