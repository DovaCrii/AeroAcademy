from urllib.parse import unquote

from django.contrib import auth
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from . import services
from .forms import SignupForm
from .models import PersonStatus

LOGIN_ERROR = "Correo o contraseña incorrectos."
LOGIN_WAIT = "Demasiados intentos. Espera unos 15 minutos y vuelve a intentar."


def waiting(request):
    """Pantalla para quien aún no fue aprobada. Si ya lo está, va a la portada."""
    if request.user.is_approved:
        return redirect("core:home")
    return render(request, "accounts/waiting.html")


def safe_next(request, candidate: str) -> str:
    """Solo rutas locales: `//evil.com`, `/\\evil.com`, esquemas y otros hosts se descartan."""
    candidate = (candidate or "").strip()
    if (
        candidate
        and "\\" not in unquote(candidate)
        and candidate.startswith("/")
        and url_has_allowed_host_and_scheme(
            candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    ):
        return candidate
    return ""


def has_password_session(request) -> bool:
    return request.user.is_authenticated and (
        request.session.get(auth.BACKEND_SESSION_KEY) == services.PASSWORD_BACKEND
    )


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "")


def _next_of(request) -> str:
    return safe_next(request, request.POST.get("next") or request.GET.get("next", ""))


def _login_context(request, **extra):
    return {
        "next": _next_of(request),
        "via_tailscale": request.user.is_authenticated and not has_password_session(request),
        **extra,
    }


@never_cache
def welcome(request):
    """Portada pública: quien no trae identidad de Tailscale llega aquí desde cualquier página protegida."""
    if request.user.is_authenticated:
        return redirect(_next_of(request) or "core:home")
    return render(request, "accounts/welcome.html", _login_context(request))


@never_cache
@require_http_methods(["GET", "POST"])
def login(request):
    """Correo + contraseña. Error genérico, límite de intentos por IP y correo, `next` validado."""
    if has_password_session(request):
        return redirect(_next_of(request) or "core:home")
    if request.method == "GET":
        return render(request, "accounts/login.html", _login_context(request))

    email = services.normalize_login(request.POST.get("email", ""))[:254]
    password = request.POST.get("password", "")[:256]
    ip = _client_ip(request)
    if services.login_blocked(ip, email):
        return render(
            request,
            "accounts/login.html",
            _login_context(request, error=LOGIN_WAIT, email=email),
            status=429,
        )
    person = auth.authenticate(request, username=email, password=password)
    if person is None or person.status != PersonStatus.APPROVED:
        services.register_login_failure(ip, email)
        return render(
            request,
            "accounts/login.html",
            _login_context(request, error=LOGIN_ERROR, email=email),
        )
    services.clear_login_failures(ip, email)
    auth.login(request, person, backend=services.PASSWORD_BACKEND)
    return redirect(_next_of(request) or "core:home")


@require_POST
def logout(request):
    auth.logout(request)
    return redirect("accounts:welcome")


@never_cache
@require_http_methods(["GET", "POST"])
def signup(request, token):
    """Registro con el enlace del admin. Cualquier fallo del enlace muestra la misma página."""
    person = services.resolve_signup_token(token)
    if person is None:
        return _private(render(request, "accounts/signup_invalid.html", status=400))
    form = SignupForm(request.POST or None, person=person)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            fresh = services.resolve_signup_token(
                token
            )  # otro envío pudo gastar el enlace entre tanto
            if fresh is None:
                return _private(render(request, "accounts/signup_invalid.html", status=400))
            services.complete_signup(
                fresh,
                display_name=form.cleaned_data["display_name"],
                password=form.cleaned_data["password1"],
                character_class=form.cleaned_data["character_class"],
            )
        auth.login(request, fresh, backend=services.PASSWORD_BACKEND)
        return redirect("core:home")
    return _private(
        render(
            request,
            "accounts/signup.html",
            {"form": form, "person": person, "is_reset": person.has_usable_password()},
        )
    )


def _private(response):
    """La página del enlace no se cachea ni manda el enlace en `Referer` a otros sitios."""
    # `same-origin` y no `no-referrer`: con este último Chrome manda `Origin: null` en el POST y Django lo rechaza.
    response["Referrer-Policy"] = "same-origin"
    response["Cache-Control"] = "no-store"
    return response
