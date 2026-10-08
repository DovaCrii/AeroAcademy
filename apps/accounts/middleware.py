import ipaddress

from django.conf import settings
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse

from . import services
from .models import PersonStatus

LOGIN_HEADER = "HTTP_TAILSCALE_USER_LOGIN"
NAME_HEADER = "HTTP_TAILSCALE_USER_NAME"
PIC_HEADER = "HTTP_TAILSCALE_USER_PROFILE_PIC"


def _is_trusted(remote_addr: str) -> bool:
    """Solo el proxy local (`tailscale serve`) puede presentar identidad."""
    try:
        ip = ipaddress.ip_address((remote_addr or "").strip())
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ip) in settings.TRUSTED_PROXY_IPS


class TailscaleRemoteUserMiddleware(RemoteUserMiddleware):
    """Identidad desde `Tailscale-User-Login` (docs/ARQUITECTURA.md).

    - Petición que no viene de TRUSTED_PROXY_IPS: 403, con o sin encabezado.
    - Sin encabezado: 401. En desarrollo (DEBUG) se acepta DEV_REMOTE_USER.
    """

    header = LOGIN_HEADER
    force_logout_if_no_header = True
    async_capable = False  # Django 5.2 ignora la respuesta de process_request en __call__

    def __call__(self, request):
        response = self.process_request(request)
        return response if response is not None else self.get_response(request)

    def process_request(self, request):
        if not _is_trusted(request.META.get("REMOTE_ADDR", "")):
            return HttpResponseForbidden("Acceso no permitido.")

        if not request.META.get(LOGIN_HEADER, "").strip():
            dev_user = settings.DEV_REMOTE_USER if settings.DEBUG else ""
            if not dev_user:
                return HttpResponse("Se requiere identidad de Tailscale.", status=401)
            request.META[LOGIN_HEADER] = dev_user

        response = super().process_request(request)
        if response is not None:
            return response
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Acceso no permitido.")

        services.sync_identity(
            request.user,
            display_name=services.decode_header_value(request.META.get(NAME_HEADER, "")),
            avatar_url=request.META.get(PIC_HEADER, ""),
        )
        return None


class ApprovalMiddleware:
    """Una persona `pending` solo ve /espera/; una `suspended` recibe 403."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            if user.status == PersonStatus.SUSPENDED:
                return render(request, "accounts/suspended.html", status=403)
            if user.status == PersonStatus.PENDING:
                waiting = reverse("accounts:waiting")
                if request.path != waiting:
                    return redirect(waiting)
        return self.get_response(request)
