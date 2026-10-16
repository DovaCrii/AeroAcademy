import ipaddress
from urllib.parse import unquote

from django.contrib import auth, messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from . import ratelimit, services, team_link, totp, two_factor
from .forms import AccountPasswordChangeForm, SignupForm, TeamSignupForm
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
    """IP del cliente para los límites de intentos. En la puerta pública `REMOTE_ADDR` es siempre el proxy local:
    se usa el último valor de `X-Forwarded-For`, que es el que agrega el propio proxy de Tailscale (los anteriores
    los puede escribir el cliente). Si no hay uno válido, se cae a `REMOTE_ADDR`."""
    remote = request.META.get("REMOTE_ADDR", "")
    if getattr(request, "public_door", False):
        last = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
        try:
            return str(ipaddress.ip_address(last))
        except ValueError:
            pass
    return remote


def _login(request, person) -> None:
    """Inicia la sesión por contraseña. El segundo factor nunca se hereda: cada inicio de sesión lo vuelve a pedir."""
    auth.login(request, person, backend=services.PASSWORD_BACKEND)
    request.session[two_factor.SESSION_KEY] = False


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
    _login(request, person)
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
    if request.method == "POST":
        ip = _client_ip(request)
        if ratelimit.blocked(
            "signup",
            ip,
            limit=SIGNUP_MAX,
        ):
            return _private(
                render(request, "accounts/signup_invalid.html", {"wait": LOGIN_WAIT}, status=429)
            )
        ratelimit.hit("signup", ip, window=services.LOGIN_WINDOW_SECONDS)
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
        _login(request, fresh)
        return redirect("core:home")
    return _private(
        render(
            request,
            "accounts/signup.html",
            {"form": form, "person": person, "is_reset": person.has_usable_password()},
        )
    )


SIGNUP_MAX = 20  # envíos por IP y 15 minutos al registro con enlace personal
TEAM_WAIT = "Demasiados intentos con este enlace. Espera unos 15 minutos y vuelve a intentar."


@never_cache
@require_http_methods(["GET", "POST"])
def team_signup(request, token):
    """Inscripción con el enlace del equipo (D35). Cualquier fallo del enlace muestra la misma página."""
    link = team_link.resolve(token)
    if link is None:
        return _private(render(request, "accounts/team_signup_invalid.html", status=400))
    if request.method == "GET":
        return _private(
            render(request, "accounts/team_signup.html", {"form": TeamSignupForm(), "link": link})
        )

    ip = _client_ip(request)
    form = TeamSignupForm(request.POST)
    if team_link.blocked(ip, link):
        return _private(
            render(
                request,
                "accounts/team_signup.html",
                {"form": form, "link": link, "wait": TEAM_WAIT},
                status=429,
            )
        )
    team_link.register_submission(ip, link)
    if not form.is_valid():
        return _private(render(request, "accounts/team_signup.html", {"form": form, "link": link}))

    data = form.cleaned_data
    result = team_link.enroll(
        link,
        login=data["email"],
        display_name=data["display_name"],
        password=data["password1"],
        character_class=data["character_class"],
    )
    if result.kind == team_link.LOGGED_IN:
        _login(request, result.person)
        return redirect("core:home")
    # Una sola respuesta para todos los casos (A12): ni el texto ni el código dependen de `result.kind`.
    return _private(render(request, "accounts/team_signup_result.html"))


def _private(response):
    """La página del enlace no se cachea ni manda el enlace en `Referer` a otros sitios."""
    # `same-origin` y no `no-referrer`: con este último Chrome manda `Origin: null` en el POST y Django lo rechaza.
    response["Referrer-Policy"] = "same-origin"
    response["Cache-Control"] = "no-store"
    return response


TOTP_WAIT = "Demasiados intentos. Espera unos 15 minutos y vuelve a intentar."


@never_cache
@require_http_methods(["GET", "POST"])
def verify(request):
    """Segundo paso de la puerta pública: código de la app o de recuperación. Solo para lead y admin."""
    if not getattr(request, "public_door", False) or not request.user.is_authenticated:
        return redirect("core:home")
    person = request.user
    nxt = _next_of(request)
    if not two_factor.needs_second_factor(person) or request.session.get(two_factor.SESSION_KEY):
        return redirect(nxt or "core:home")
    if not two_factor.is_enrolled(person):
        return render(request, "accounts/totp_blocked.html", status=403)
    if request.method == "GET":
        return render(request, "accounts/totp_verify.html", {"next": nxt})
    ip = _client_ip(request)
    if two_factor.check_blocked(person, ip):
        return render(
            request, "accounts/totp_verify.html", {"next": nxt, "error": TOTP_WAIT}, status=429
        )
    if two_factor.verify_login(person, request.POST.get("code", "")[:32], ip):
        request.session.cycle_key()
        request.session[two_factor.SESSION_KEY] = True
        return redirect(nxt or "core:home")
    return render(
        request,
        "accounts/totp_verify.html",
        {"next": nxt, "error": "Código incorrecto o ya usado."},
        status=400,
    )


@never_cache
@require_http_methods(["GET", "POST"])
def two_factor_setup(request):
    """Activar, ver o desactivar el segundo factor. Solo por la puerta de la tailnet (en la pública no existe)."""
    if getattr(request, "public_door", False):
        raise Http404("No encontrado.")
    person = request.user
    ctx = {"enrolled": two_factor.is_enrolled(person)}
    if request.method == "POST":
        action = request.POST.get("action", "")
        code = request.POST.get("code", "")[:32]
        ip = _client_ip(request)
        if two_factor.check_blocked(person, ip):
            ctx["error"] = TOTP_WAIT
            return render(
                request, "accounts/two_factor.html", _setup_context(person, ctx), status=429
            )
        if action == "confirm":
            codes = two_factor.confirm_enrollment(person, code)
            if codes is None:
                ratelimit.hit("totp", str(person.pk), window=two_factor.WINDOW_SECONDS)
                ctx["error"] = "Código incorrecto. Revisa que la hora del teléfono sea automática."
            else:
                ctx.update(enrolled=True, recovery_codes=codes)
        elif action in {"regenerate", "disable"}:
            if two_factor.verify_login(person, code, ip):
                if action == "disable":
                    two_factor.disable(person)
                    ctx["enrolled"] = False
                else:
                    ctx["recovery_codes"] = two_factor.regenerate_recovery(person)
            else:
                ctx["error"] = "Código incorrecto o ya usado."
    return render(request, "accounts/two_factor.html", _setup_context(person, ctx))


def _setup_context(person, ctx):
    if not ctx.get("enrolled"):
        device = two_factor.begin_enrollment(person)
        ctx["secret"] = totp.group(device.secret)
        ctx["otpauth"] = totp.otpauth_uri(device.secret, person.login)
    else:
        ctx["recovery_left"] = two_factor.recovery_left(person)
    return ctx


PASSWORD_CHANGE_MAX = 5  # intentos con la contraseña actual equivocada por persona y 15 minutos


@never_cache
def account(request):
    """«Mi cuenta»: correo, puerta, rol y qué acciones de seguridad corresponden a esta sesión."""
    person = request.user
    return render(
        request,
        "accounts/account.html",
        {
            "person": person,
            "door_public": getattr(request, "public_door", False),
            "can_change_password": has_password_session(request),
            "can_two_factor": not getattr(request, "public_door", False),
            "two_factor_enrolled": two_factor.is_enrolled(person),
        },
    )


@never_cache
@require_http_methods(["GET", "POST"])
def password_change(request):
    """Cambio de contraseña. Solo con sesión por contraseña: quien entra por Tailscale no tiene contraseña que cambiar."""
    if not has_password_session(request):
        raise Http404("No encontrado.")
    person = request.user
    form = AccountPasswordChangeForm(person, request.POST or None)
    if request.method == "POST":
        if ratelimit.blocked("pwchange", str(person.pk), limit=PASSWORD_CHANGE_MAX):
            return render(
                request,
                "accounts/password_change.html",
                {"form": form, "wait": LOGIN_WAIT},
                status=429,
            )
        if form.is_valid():
            form.save()
            auth.update_session_auth_hash(request, person)
            ratelimit.clear("pwchange", str(person.pk))
            messages.success(request, "Listo, cambiaste tu contraseña.")
            return redirect("accounts:account")
        if "old_password" in form.errors:
            ratelimit.hit("pwchange", str(person.pk), window=services.LOGIN_WINDOW_SECONDS)
    return render(request, "accounts/password_change.html", {"form": form})
