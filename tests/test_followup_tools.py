import importlib.util
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.assistant import client, followup, search
from apps.credentials import services as creds
from apps.notifications.models import Notification
from apps.paths.models import LearningPath, Milestone
from apps.progress import services as progress

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
ROOT = Path(settings.BASE_DIR)


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)
    yield
    client.TRANSPORT = None


def old(person, days=30):
    """La cuenta tiene más de una semana."""
    person.__class__.objects.filter(pk=person.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )
    person.refresh_from_db()
    return person


def nudges(person):
    return Notification.objects.filter(recipient=person, kind="teo_nudge")


# --- seguimiento semanal ----------------------------------------------------------------------------------------------


def test_idle_people_get_one_nudge_per_week_with_their_mission(member):
    old(member)
    assert followup.run()[0] == 1
    n = nudges(member).get()
    assert n.url.startswith("/rutas/") and "Teo" in n.title
    assert followup.run()[0] == 0  # misma semana: no se repite
    assert nudges(member).count() == 1


def test_a_new_week_sends_a_new_nudge(member):
    old(member)
    followup.run(timezone.localdate())
    followup.run(timezone.localdate() + timedelta(days=7))
    assert nudges(member).count() == 2


def test_active_or_brand_new_people_are_left_alone(member, lead):
    old(member)
    progress.set_milestone(
        member, Milestone.objects.filter(path__slug="forma-revit", retired=False).first(), True
    )
    # `lead` es de hoy: aún no cuenta como inactiva
    assert followup.run()[0] == 0
    assert not nudges(member).exists() and not nudges(lead).exists()


def test_nobody_is_nudged_when_everything_is_done(member):
    old(member)
    LearningPath.objects.update(is_published=False)  # sin campañas visibles: no hay misión
    assert followup.run()[0] == 0


def test_the_setting_turns_it_off(member, settings):
    old(member)
    settings.TEO_NUDGES = False
    assert followup.run() == (0, 0)
    assert not Notification.objects.filter(kind="teo_nudge").exists()


def test_leads_get_a_weekly_digest_once(member, lead):
    old(member)
    cred = creds.create_credential(
        member,
        {"title": "Curso", "kind": "completion", "visibility": "team"},
        SimpleUploadedFile("c.pdf", PDF),
    )
    nudged, digests = followup.run()
    assert digests == 1 and cred
    digest = Notification.objects.get(recipient=lead, kind="teo_digest")
    assert "1 certificado(s) por revisar" in digest.body and "sin avance" in digest.body
    assert followup.run()[1] == 0


def test_followup_command_runs(member, capsys):
    old(member)
    call_command("teo_seguimiento")
    assert "Avisos de Teo: 1" in capsys.readouterr().out


def test_nothing_leaves_the_vm_when_following_up(member):
    seen = []
    client.TRANSPORT = httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200, json={}))
    old(member)
    followup.run()
    assert seen == []


# --- probar la conexión --------------------------------------------------------------------------------------------------


def test_teo_probar_reports_success_without_showing_the_key(settings, capsys):
    settings.NIM_API_KEY = "nvapi-SECRETA-123"
    client.TRANSPORT = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hola, soy Teo."}}],
                "usage": {"total_tokens": 9},
            },
        )
    )
    call_command("teo_probar")
    out = capsys.readouterr().out
    assert "OK en" in out and "Hola, soy Teo." in out and "SECRETA" not in out


@pytest.mark.parametrize(
    ("status", "hint"), [(401, "NIM_API_KEY"), (429, "Límite"), (500, "NIM_MODEL")]
)
def test_teo_probar_explains_failures(settings, status, hint):
    settings.NIM_API_KEY = "nvapi-X"
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(status, json={}))
    with pytest.raises(CommandError, match=hint):
        call_command("teo_probar")


def test_teo_probar_needs_a_key(settings):
    settings.NIM_API_KEY = ""
    with pytest.raises(CommandError, match="NIM_API_KEY"):
        call_command("teo_probar")


# --- ayuda con búsqueda local ----------------------------------------------------------------------------------------------


def test_help_search_works_without_the_model(client_for, member, settings):
    settings.NIM_API_KEY = ""
    html = client_for(member.login).get("/ayuda/?q=certificado").content.decode()
    assert "Resultados para" in html and "Cómo subo un certificado" in html


def test_help_search_with_no_results_offers_the_forum(client_for, member):
    html = client_for(member.login).get("/ayuda/?q=zzzxqy").content.decode()
    assert "No encontré nada" in html and "/foro/nuevo/?titulo=zzzxqy" in html


def test_help_search_ignores_notes_and_threads(client_for, member, lead):
    from apps.community import services as notes

    notes.create_note(
        lead, LearningPath.objects.get(slug="forma-revit"), "texto-reservado zafiro", "tip"
    )
    search.reindex()
    page = client_for(member.login).get("/ayuda/?q=zafiro").content.decode()
    assert "texto-reservado" not in page and "No encontré nada" in page


def test_new_guides_exist_and_are_indexed(client_for, member):
    for slug in (
        "primeros-pasos",
        "teo-el-asistente",
        "vencimientos-y-exportacion",
        "documentos-y-conocimiento",
        "equipo-y-tablero",
        "moderacion-y-avisos",
    ):
        assert client_for(member.login).get(f"/ayuda/{slug}/").status_code == 200
    assert any(h["kind"] == "help" for h in search.search("semana avanzar Teo avisa"))


def test_resources_are_found_by_their_skills():
    search.reindex()
    hits = search.search("LiDAR")
    assert any(h["kind"] == "resource" for h in hits) or search.search("nubes de puntos")


# --- atuendo de Teo -----------------------------------------------------------------------------------------------------


def test_teo_dresses_for_the_world_of_the_path(client_for, member, settings):
    settings.NIM_API_KEY = "nvapi-X"
    client = client_for(member.login)
    assert "teo-idle.svg" in client.get("/").content.decode()
    assert "teo-architecture.svg" in client.get("/rutas/forma-revit/").content.decode()
    assert "teo-civil.svg" in client.get("/rutas/bentley-learn/").content.decode()
    settings.NIM_API_KEY = ""
    assert "teo-sleep.svg" in client.get("/rutas/forma-revit/").content.decode()


def test_every_sprite_teo_can_wear_exists():
    folder = ROOT / "apps" / "core" / "static" / "game" / "teo"
    for name in (
        "idle",
        "happy",
        "thinking",
        "sleep",
        "celebra",
        "architecture",
        "civil",
        "survey",
        "mechanical",
        "aero",
    ):
        assert (folder / f"teo-{name}.svg").is_file(), name


# --- tools/fusionar_cadena.py ------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def merge_tool():
    spec = importlib.util.spec_from_file_location(
        "fusionar_cadena", ROOT / "tools" / "fusionar_cadena.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pr(number, base, head, checks=("SUCCESS",), **extra):
    return {
        "number": number,
        "title": f"PR {number}",
        "baseRefName": base,
        "headRefName": head,
        "mergeable": "MERGEABLE",
        "isDraft": False,
        "statusCheckRollup": [{"conclusion": c} for c in checks],
        **extra,
    }


def test_chain_is_ordered_from_main_up(merge_tool):
    prs = [pr(3, "b2", "b3"), pr(1, "main", "b1"), pr(2, "b1", "b2")]
    assert [p["number"] for p in merge_tool.build_chain(prs)] == [1, 2, 3]


def test_a_forked_or_loose_chain_is_refused(merge_tool):
    with pytest.raises(ValueError, match="Dos PR"):
        merge_tool.build_chain([pr(1, "main", "b1"), pr(2, "b1", "b2"), pr(3, "b1", "b3")])
    with pytest.raises(ValueError, match="fuera de la cadena"):
        merge_tool.build_chain([pr(1, "main", "b1"), pr(2, "otra", "b2")])


def test_ci_and_conflicts_block_a_pr(merge_tool):
    assert merge_tool.problems(pr(1, "main", "b1")) == []
    assert "CI fallo" in merge_tool.problems(pr(1, "main", "b1", checks=("SUCCESS", "FAILURE")))
    assert "CI pendiente" in merge_tool.problems(pr(1, "main", "b1", checks=("SUCCESS", "")))
    assert "CI pendiente" in merge_tool.problems(pr(1, "main", "b1", checks=()))
    assert "tiene conflictos" in merge_tool.problems(pr(1, "main", "b1", mergeable="CONFLICTING"))
    assert "es un borrador" in merge_tool.problems(pr(1, "main", "b1", isDraft=True))


def test_dry_run_changes_nothing_and_execute_needs_confirmation(merge_tool, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(merge_tool, "open_prs", lambda: [pr(1, "main", "b1"), pr(2, "b1", "b2")])
    monkeypatch.setattr(merge_tool, "gh", lambda *a, **k: calls.append(a) or "")
    assert merge_tool.main([]) == 0 and calls == []
    assert "Simulación" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(SystemExit, match="Cancelado"):
        merge_tool.main(["--ejecutar"])
    assert calls == []


def test_execute_retargets_and_merges_in_order_with_merge_commits(merge_tool, monkeypatch):
    calls = []
    monkeypatch.setattr(
        merge_tool, "open_prs", lambda: [pr(1, "main", "b1"), pr(2, "b1", "b2"), pr(3, "b2", "b3")]
    )
    monkeypatch.setattr(merge_tool, "wait_ready", lambda n: calls.append(("wait", n)))
    monkeypatch.setattr(merge_tool, "gh", lambda *a, **k: calls.append(a) or "")
    monkeypatch.setattr("builtins.input", lambda _: "FUSIONAR 3")
    assert merge_tool.main(["--ejecutar"]) == 0
    assert calls == [
        ("pr", "merge", "1", "--merge"),
        ("pr", "edit", "2", "--base", "main"), ("wait", 2), ("pr", "merge", "2", "--merge"),
        ("pr", "edit", "3", "--base", "main"), ("wait", 3), ("pr", "merge", "3", "--merge"),
    ]  # fmt: skip
    assert not any("--squash" in c or "--rebase" in c for c in calls if isinstance(c, tuple))


def test_execute_refuses_when_a_pr_is_not_ready(merge_tool, monkeypatch):
    monkeypatch.setattr(merge_tool, "open_prs", lambda: [pr(1, "main", "b1", checks=("FAILURE",))])
    monkeypatch.setattr(merge_tool, "gh", lambda *a, **k: pytest.fail("no debe tocar nada"))
    with pytest.raises(SystemExit, match="no están listos"):
        merge_tool.main(["--ejecutar"])


def test_upto_limits_the_merge(merge_tool, monkeypatch):
    calls = []
    monkeypatch.setattr(
        merge_tool, "open_prs", lambda: [pr(1, "main", "b1"), pr(2, "b1", "b2"), pr(3, "b2", "b3")]
    )
    monkeypatch.setattr(merge_tool, "wait_ready", lambda n: None)
    monkeypatch.setattr(merge_tool, "gh", lambda *a, **k: calls.append(a) or "")
    monkeypatch.setattr("builtins.input", lambda _: "FUSIONAR 2")
    merge_tool.main(["--ejecutar", "--hasta", "2"])
    assert [c for c in calls if c[1] == "merge"] == [
        ("pr", "merge", "1", "--merge"),
        ("pr", "merge", "2", "--merge"),
    ]


# --- el despliegue conoce lo nuevo --------------------------------------------------------------------------------------------


def test_the_installer_wires_the_teo_timer_and_the_env_file():
    install = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "centro-teo.timer" in install and "deploy/centro.env" in install
    assert "teo_seguimiento" in (ROOT / "deploy" / "centro-teo.service").read_text(encoding="utf-8")
    assert "deploy/centro.env" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_the_env_template_lists_every_setting_and_marks_what_to_paste():
    text = (ROOT / "deploy" / "centro.env.plantilla").read_text(encoding="utf-8")
    for key in (
        "SECRET_KEY",
        "ALLOWED_HOSTS",
        "BOOTSTRAP_ADMINS",
        "NIM_API_KEY",
        "NIM_MODEL",
        "BOT_DAILY_LIMIT",
        "TEO_NUDGES",
        "DATABASE_PATH",
        "MEDIA_ROOT",
    ):
        assert f"\n{key}=" in "\n" + text, key
    assert text.count("PEGA") >= 3
    assert "nvapi-" not in text  # nunca una clave, ni de ejemplo


# --- diagnóstico de la conexión (error real en p340: «http» sin más detalle) --------------------------------------------


def test_teo_probar_shows_the_http_status_and_the_api_message(settings):
    settings.NIM_API_KEY = "nvapi-X"
    client.TRANSPORT = httpx.MockTransport(
        lambda r: httpx.Response(404, json={"detail": "Function not found for account"})
    )
    with pytest.raises(CommandError) as exc:
        call_command("teo_probar")
    assert "HTTP 404" in str(exc.value) and "Function not found for account" in str(exc.value)
    assert "nvapi-X" not in str(exc.value)


@pytest.mark.parametrize(
    "body",
    [
        {"error": {"message": "modelo inexistente"}},
        {"message": "modelo inexistente"},
        {"title": "modelo inexistente"},
    ],
)
def test_error_detail_understands_the_usual_shapes(settings, body):
    settings.NIM_API_KEY = "nvapi-X"
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(400, json=body))
    with pytest.raises(client.BotError) as exc:
        client.chat([{"role": "user", "content": "hola"}])
    assert exc.value.status == 400 and exc.value.detail == "modelo inexistente"


def test_the_error_detail_is_not_stored_in_the_log(member, settings):
    from apps.assistant import services
    from apps.assistant.models import BotLog

    settings.NIM_API_KEY = "nvapi-X"
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(404, json={"detail": "algo"}))
    services.answer(member, "hola teo")
    assert BotLog.objects.get().error == "http"
    assert "algo" not in repr(list(BotLog.objects.values()))


def test_teo_probar_lists_models_and_flags_a_missing_one(settings, capsys):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL = "meta/modelo-que-no-existe"
    models = {
        "data": [
            {"id": "meta/llama-3.1-8b-instruct"},
            {"id": "nvidia/embed-qa"},
            {"id": "mistralai/mixtral-8x7b-instruct-v0.1"},
        ]
    }
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(200, json=models))
    call_command("teo_probar", "--modelos")
    out = capsys.readouterr().out
    assert "meta/llama-3.1-8b-instruct" in out and "mixtral" in out and "embed-qa" not in out
    assert "NO está en la lista" in out and "nvapi-X" not in out


def test_teo_probar_marks_the_configured_model(settings, capsys):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL = "meta/llama-3.1-8b-instruct"
    client.TRANSPORT = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": [{"id": "meta/llama-3.1-8b-instruct"}]})
    )
    call_command("teo_probar", "--modelos")
    out = capsys.readouterr().out
    assert "el configurado" in out and "NO está" not in out


def test_listing_models_reports_auth_errors(settings):
    settings.NIM_API_KEY = "nvapi-X"
    client.TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(401, json={}))
    with pytest.raises(CommandError, match="rechazada"):
        call_command("teo_probar", "--modelos")


# --- modelos retirados por NIM (error real en p340: HTTP 410, fin de vida de llama-3.3-70b) ------------------------------


def _router(statuses, seen):
    """Transporte que responde según el modelo pedido: {modelo: código}; lo demás, 200."""
    import json

    def handler(request):
        model = json.loads(request.content)["model"]
        seen.append(model)
        code = statuses.get(model, 200)
        if code != 200:
            return httpx.Response(
                code, json={"detail": f"The model '{model}' has reached its end of life"}
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": f"hola desde {model}"}}],
                "usage": {"total_tokens": 5},
            },
        )

    return httpx.MockTransport(handler)


def test_a_retired_model_falls_back_to_the_next_one(settings):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL, settings.NIM_MODEL_FALLBACKS = "viejo/uno", ["viejo/dos", "vigente/tres"]
    seen = []
    client.TRANSPORT = _router({"viejo/uno": 410, "viejo/dos": 404}, seen)
    text, _, _ = client.chat([{"role": "user", "content": "hola"}])
    assert seen == ["viejo/uno", "viejo/dos", "vigente/tres"] and text == "hola desde vigente/tres"
    assert client.last_model == "vigente/tres"


def test_teo_keeps_answering_when_the_main_model_is_gone(member, settings):
    from apps.assistant import services

    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL, settings.NIM_MODEL_FALLBACKS = "viejo/uno", ["vigente/dos"]
    client.TRANSPORT = _router({"viejo/uno": 410}, [])
    answer = services.answer(member, "hola teo")
    assert answer.status == "ok" and "vigente/dos" in answer.text


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_other_errors_do_not_try_other_models(settings, status):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL, settings.NIM_MODEL_FALLBACKS = "uno/a", ["dos/b"]
    seen = []
    client.TRANSPORT = _router({"uno/a": status}, seen)
    with pytest.raises(client.BotError):
        client.chat([{"role": "user", "content": "hola"}])
    assert seen == ["uno/a"]


def test_when_every_model_is_gone_the_error_is_reported(settings):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL, settings.NIM_MODEL_FALLBACKS = "a/1", ["b/2"]
    client.TRANSPORT = _router({"a/1": 410, "b/2": 410}, [])
    with pytest.raises(client.BotError) as exc:
        client.chat([{"role": "user", "content": "hola"}])
    assert exc.value.status == 410


def test_the_default_model_is_not_the_retired_one():
    assert settings.NIM_MODEL != "meta/llama-3.3-70b-instruct"
    assert "meta/llama-3.3-70b-instruct" not in settings.NIM_MODEL_FALLBACKS
    text = (ROOT / "deploy" / "centro.env.plantilla").read_text(encoding="utf-8")
    assert "llama-3.3" not in text and "NIM_MODEL_FALLBACKS=" in text


def test_teo_probar_reports_which_model_answered(settings, capsys):
    settings.NIM_API_KEY = "nvapi-X"
    settings.NIM_MODEL, settings.NIM_MODEL_FALLBACKS = "viejo/uno", ["vigente/dos"]
    client.TRANSPORT = _router({"viejo/uno": 410}, [])
    call_command("teo_probar")
    assert "modelo vigente/dos" in capsys.readouterr().out


# --- diagnóstico en la VM -------------------------------------------------------------------------------------------------


def test_the_diagnostic_script_checks_everything_and_changes_nothing():
    text = (ROOT / "deploy" / "diagnostico.sh").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash") and "\r" not in text
    for needle in (
        "tailscaled-aeroacademy",
        "serve status",
        "CertDomains",
        "cert --cert-file",
        "healthz",
        "journalctl",
        "HTTPS Certificates",
        "Machines",
    ):
        assert needle in text, needle
    for forbidden in (
        "systemctl restart",
        "systemctl stop",
        "rm -rf /",
        "serve reset",
        "funnel",
        " up --",
    ):
        assert forbidden not in text, forbidden
