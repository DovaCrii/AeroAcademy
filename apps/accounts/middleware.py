import hashlib
import ipaddress
import logging

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.cache import cache
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from . import services, two_factor
from .models import PersonStatus

logger = logging.getLogger("apps.accounts")

LOGIN_HEADER = "HTTP_TAILSCALE_USER_LOGIN"
NAME_HEADER = "HTTP_TAILSCALE_USER_NAME"
PIC_HEADER = "HTTP_TAILSCALE_USER_PROFILE_PIC"
HEALTH_PATH = "/healthz"
# Bandera de sesión que deja `POST /salir/` en la tailnet: mientras esté puesta, el encabezado de Tailscale no
# inicia sesión solo (D41). No da acceso a nada; solo `POST /entrar/tailscale/` la borra.
TS_SIGNED_OUT = "ts_signed_out"
TAILSCALE_BACKEND = "apps.accounts.backends.TailscaleBackend"
# Páginas que puede ver quien aún no entró (bienvenida, entrar, salir, registro con enlace del admin).
PUBLIC_PREFIXES = ("/bienvenida/", "/entrar/", "/salir/", "/registro/", "/inscripcion/")


def _is_trusted(remote_addr: str) -> bool:
    """Solo el proxy local (`tailscale serve`) puede presentar identidad."""
    try:
        ip = ipaddress.ip_address((remote_addr or "").strip())
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ip) in settings.TRUSTED_PROXY_IPS


def _has_password_session(request) -> bool:
    user = request.user
    return (
        user.is_authenticated
        and request.session.get(auth.BACKEND_SESSION_KEY, TAILSCALE_BACKEND) != TAILSCALE_BACKEND
    )


class PublicDoorMiddleware:
    """Puerta pública (D36, Funnel). La decide el proceso (`settings.PUBLIC_DOOR`), nunca la petición.

    En la puerta pública se borran los encabezados de identidad de Tailscale (aunque alguien los mande), y
    `/admin/`, la moderación y la gestión de personas responden 404. En la puerta de la tailnet no cambia nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.public_door = bool(settings.PUBLIC_DOOR)
        if request.public_door:
            for name in (LOGIN_HEADER, NAME_HEADER, PIC_HEADER):
                request.META.pop(name, None)
            path = request.path
            if path.startswith(settings.PUBLIC_BLOCKED_PREFIXES) or "/moderar" in path:
                raise Http404("No encontrado.")
        return self.get_response(request)


class TailscaleRemoteUserMiddleware(RemoteUserMiddleware):
    """Identidad desde `Tailscale-User-Login` o, si no hay encabezado, desde la sesión por contraseña (D34).

    - Petición que no viene de TRUSTED_PROXY_IPS: 403, con o sin encabezado.
    - Con encabezado y sin sesión por contraseña: entra como siempre (crea a la persona `pending`).
    - Con sesión por contraseña: se conserva siempre. Un encabezado que identifica a otra persona NO la
      reemplaza (queda en el registro, sin correos). Sin encabezado, la sesión no se cierra.
    - Tras «Salir» en la tailnet (bandera `ts_signed_out`) el encabezado se ignora hasta «Entrar con Tailscale».
    - Sin encabezado ni sesión: páginas públicas, o redirección a /bienvenida/. DEV_REMOTE_USER (DEBUG) simula el encabezado.
    """

    header = LOGIN_HEADER
    force_logout_if_no_header = False
    async_capable = False  # Django 5.2 ignora la respuesta de process_request en __call__

    def __call__(self, request):
        response = self.process_request(request)
        return response if response is not None else self.get_response(request)

    def process_request(self, request):
        if not _is_trusted(request.META.get("REMOTE_ADDR", "")):
            return HttpResponseForbidden("Acceso no permitido.")

        if (
            request.path == HEALTH_PATH
        ):  # solo desde el proxy local: lo usa el instalador y el monitoreo
            return None

        if getattr(request, "public_door", False):
            return self._public_door(request)

        header_login = request.META.get(LOGIN_HEADER, "").strip()
        if not header_login and settings.DEBUG:
            header_login = settings.DEV_REMOTE_USER

        if not _has_password_session(request) and request.session.get(TS_SIGNED_OUT):
            # Salió a propósito: el encabezado no la vuelve a iniciar sola (D41).
            header_login = ""

        if _has_password_session(request):
            if header_login and services.normalize_login(header_login) != request.user.login:
                self._log_mismatch(request, header_login)
                return None
            if header_login:  # el mismo correo: se actualizan nombre y foto como siempre
                self._sync(request)
            return None

        if header_login:
            request.META[LOGIN_HEADER] = header_login
            response = super().process_request(request)
            if response is not None:
                return response
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Acceso no permitido.")
            self._sync(request)
            return None

        if request.user.is_authenticated or request.path.startswith(PUBLIC_PREFIXES):
            return None
        target = reverse("accounts:welcome")
        if request.method == "GET":
            target += "?" + urlencode({"next": request.get_full_path()})
        return redirect(target)

    @staticmethod
    def _public_door(request):
        """Sin Tailscale: solo vale la sesión por contraseña. Una sesión de otra clase se cierra."""
        if request.user.is_authenticated and not _has_password_session(request):
            auth.logout(request)
        if request.user.is_authenticated or request.path.startswith(PUBLIC_PREFIXES):
            return None
        target = reverse("accounts:welcome")
        if request.method == "GET":
            target += "?" + urlencode({"next": request.get_full_path()})
        return redirect(target)

    @staticmethod
    def _sync(request):
        services.sync_identity(
            request.user,
            display_name=services.decode_header_value(request.META.get(NAME_HEADER, "")),
            avatar_url=request.META.get(PIC_HEADER, ""),
        )

    @staticmethod
    def _log_mismatch(request, header_login):
        """Una vez por hora por pareja (sin guardar correos): el encabezado no toma el lugar de la sesión."""
        digest = hashlib.sha256(services.normalize_login(header_login).encode()).hexdigest()[:12]
        if cache.add(f"hdr-mismatch:{request.user.pk}:{digest}", 1, 3600):
            logger.warning(
                "El encabezado de Tailscale identifica a una persona distinta de la sesión por "
                "contraseña (persona %s); se mantiene la sesión.",
                request.user.pk,
            )


class ApprovalMiddleware:
    """Una persona `pending` solo ve /espera/; una `suspended` recibe 403."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            if user.status == PersonStatus.SUSPENDED and request.path != reverse("accounts:logout"):
                return render(request, "accounts/suspended.html", status=403)
            if user.status == PersonStatus.PENDING:
                waiting = reverse("accounts:waiting")
                if request.path not in (
                    waiting,
                    reverse("accounts:logout"),
                ):  # «Salir» sirve estando en espera
                    return redirect(waiting)
        return self.get_response(request)


class PublicSecondFactorMiddleware:
    """En la puerta pública, quien es lead o admin debe pasar el segundo factor (TOTP) antes de ver nada más.

    - Con TOTP activado y sin verificar en esta sesión: va a /verificar/.
    - Sin TOTP activado: página de bloqueo (se activa entrando por la tailnet).
    """

    EXEMPT = ("/verificar/", "/salir/", HEALTH_PATH)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            getattr(request, "public_door", False)
            and user is not None
            and user.is_authenticated
            and user.status == PersonStatus.APPROVED
            and two_factor.needs_second_factor(user)
            and not request.session.get(two_factor.SESSION_KEY)
            and not request.path.startswith(self.EXEMPT)
        ):
            if two_factor.is_enrolled(user):
                target = reverse("accounts:verify")
                if request.method == "GET":
                    target += "?" + urlencode({"next": request.get_full_path()})
                return redirect(target)
            return render(request, "accounts/totp_blocked.html", status=403)
        return self.get_response(request)
