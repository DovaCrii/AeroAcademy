from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from . import assessment, constants, data, services
from .models import KnowledgeAttempt


def _context(**extra):
    return {
        "pass_percent": assessment.PASS_PERCENT,
        "per_attempt": assessment.QUESTIONS_PER_ATTEMPT,
        "valid_months": assessment.VALID_MONTHS,
        **extra,
    }


@require_GET
def home(request):
    """Operaciones RPAS en JEJ: el proceso para todos, con infografías, y el avance de cada quien."""
    overview = data.load_overview()
    return render(
        request,
        "dgac/home.html",
        _context(
            overview=overview,
            sections=(overview or {}).get("sections", []),
            installed=overview is not None,
            summary=services.progress_summary(request.user),
            bank_ok=data.bank_is_available(),
        ),
    )


@require_GET
def asset(request, name):
    """Infografías del contenido privado: solo para personas aprobadas (el middleware ya lo exige), nunca estáticas."""
    path = data.image_path(name)
    if path is None:
        raise Http404
    response = FileResponse(path.open("rb"), content_type=data.image_type(path))
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    response["Cache-Control"] = "private, max-age=300"
    return response


@require_GET
def test_home(request):
    """La prueba: reglas, historial propio y, para quien lidera, el estado del equipo."""
    attempts = list(services.attempts_of(request.user)[:20])
    return render(
        request,
        "dgac/test.html",
        _context(
            bank_ok=data.bank_is_available(),
            summary=services.progress_summary(request.user),
            attempts=attempts,
            valid=services.latest_valid(request.user),
            team=services.team_status() if request.user.is_lead else None,
        ),
    )


@require_http_methods(["GET", "POST"])
def take(request):
    """25 preguntas sorteadas. El sorteo vive en la sesión; la corrección es del servidor."""
    if not data.bank_is_available():
        return render(
            request, "dgac/not_installed.html", _context(what="el banco de preguntas"), status=503
        )

    if request.method == "POST":
        ids = services.take_draw(request.session, request.POST.get("draw", ""))
        if not ids:  # sesión vencida o POST sin sorteo: no se corrige a ciegas
            return redirect("dgac:take")
        given = {qid: request.POST.get(f"q{qid}", "") for qid in ids}
        attempt = services.submit_attempt(request.user, ids, given)
        return redirect("dgac:result", pk=attempt.pk)

    token, questions = services.open_draw(request.session)
    for number, q in enumerate(questions, start=1):
        q["number"] = number
        q["lines"] = assessment.enumerated_lines(q["text"])
    return render(
        request,
        "dgac/take.html",
        _context(token=token, questions=questions, total=len(questions)),
    )


def _attempt_or_404(request, pk):
    attempt = get_object_or_404(KnowledgeAttempt.objects.select_related("person"), pk=pk)
    if not services.can_view(request.user, attempt):
        raise Http404  # no se revela que existe
    return attempt


def _review_rows(attempt):
    rows = []
    for r in attempt.answers:
        rows.append(
            {
                **r,
                "lines": assessment.enumerated_lines(r["text"]),
                "given_text": assessment.option_text(r, r["given"]),
                "answer_text": assessment.option_text(r, r["answer"]),
            }
        )
    return rows


@require_GET
def result(request, pk):
    attempt = _attempt_or_404(request, pk)
    rows = _review_rows(attempt)
    percent = float(attempt.score_percent)
    return render(
        request,
        "dgac/result.html",
        _context(
            attempt=attempt,
            rows=rows,
            wrong=[r for r in rows if not r["correct"]],
            topics=assessment.reinforce(attempt.answers),
            gauge=round(percent * 3.14159 * 2 * 54 / 100, 1),  # circunferencia del medidor (r = 54)
            own=attempt.person_id == request.user.pk,
        ),
    )


@require_GET
def diploma(request, pk):
    """Diploma interno imprimible. Solo existe para intentos aprobados."""
    attempt = _attempt_or_404(request, pk)
    if not attempt.passed:
        raise Http404
    return render(
        request,
        "dgac/diploma.html",
        _context(
            attempt=attempt,
            title=services.diploma_title(),
            text=services.diploma_text(),
            issuer=constants.DEFAULT_ISSUER,
            back=reverse("dgac:result", args=[attempt.pk]),
        ),
    )
