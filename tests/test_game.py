import json
from datetime import UTC, date, datetime, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.catalog.seeding import SeedError
from apps.credentials import services as creds
from apps.gamification import game, rules
from apps.gamification.models import Badge, PersonBadge, Title, XPEvent
from apps.gamification.seeding import load_game, validate_game
from apps.paths.models import LearningPath, Level, Milestone, QuizQuestion
from apps.progress import services as progress

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n" + b"x" * 200
FORMA = "forma-revit"


@pytest.fixture(autouse=True)
def seeded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_catalog", verbosity=0)


def xp(person):
    """XP sin la bonificación de racha semanal (que se suma sola al aprender)."""
    rows = XPEvent.objects.filter(person=person).exclude(kind="streak")
    return sum(r.points for r in rows)


def make_cred(owner, **extra):
    data = {"title": "Curso", "kind": "completion", "visibility": "team", **extra}
    return creds.create_credential(owner, data, SimpleUploadedFile("c.pdf", PDF))


def forma():
    return LearningPath.objects.get(slug=FORMA)


def first_milestone():
    return (
        Milestone.objects.filter(path=forma(), retired=False)
        .order_by("level__order", "order")
        .first()
    )


def badges(person):
    return game.unlocked_badges(person)


# --- niveles -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("xp", "level"),
    [(0, 1), (99, 1), (100, 2), (299, 2), (300, 3), (600, 4), (1000, 5), (2800, 8), (19000, 20)],
)
def test_level_follows_the_table(xp, level):
    assert game.level_for(xp) == level


def test_level_info_has_a_progress_bar(member):
    game.award(member, "x:1", "manual", 150)
    info = game.level_info(member)
    assert info["level"] == 2 and info["xp"] == 150
    assert (
        info["into"] == 50 and info["span"] == 200 and info["pct"] == 25 and info["to_next"] == 150
    )


# --- XP idempotente ---------------------------------------------------------------------------------------------


def test_award_is_unique_per_source(member):
    assert game.award(member, "k:1", "milestone") is True
    assert game.award(member, "k:1", "milestone") is False
    assert xp(member) == 10
    assert game.revoke(member, "k:1") is True and game.revoke(member, "k:1") is False


def test_checking_and_unchecking_a_milestone_never_duplicates_xp(member):
    m = first_milestone()
    progress.set_milestone(member, m, True)
    progress.set_milestone(member, m, True)
    assert xp(member) == 10
    progress.set_milestone(member, m, False)
    assert xp(member) == 0
    progress.set_milestone(member, m, True)
    assert xp(member) == 10
    assert "primera-luz" in badges(member)


def test_unchecking_the_only_milestone_takes_back_the_badge(member):
    m = first_milestone()
    progress.set_milestone(member, m, True)
    progress.set_milestone(member, m, False)
    assert "primera-luz" not in badges(member)


def test_a_correct_quiz_answer_gives_xp_once_and_is_kept(member):
    q = QuizQuestion.objects.filter(path=forma(), retired=False).first()
    wrong = (q.answer_index + 1) % len(q.options)
    progress.answer_question(member, q, wrong)
    assert xp(member) == 0
    progress.answer_question(member, q, q.answer_index)
    progress.answer_question(member, q, q.answer_index)
    assert xp(member) == 5
    progress.answer_question(member, q, wrong)  # cambiar luego no quita lo ganado
    assert xp(member) == 5


def test_chapter_and_path_bonuses_follow_completion(member):
    path = forma()
    for m in Milestone.objects.filter(path=path, retired=False):
        progress.set_milestone(member, m, True)
    for q in QuizQuestion.objects.filter(path=path, retired=False):
        progress.answer_question(member, q, q.answer_index)
    kinds = set(XPEvent.objects.filter(person=member).values_list("kind", flat=True))
    assert {"chapter", "path"} <= kinds
    assert XPEvent.objects.filter(person=member, source=f"path:{FORMA}").exists()
    assert "cota-0-a-certificacion" in badges(member)
    some = Milestone.objects.filter(path=path, retired=False).first()
    progress.set_milestone(member, some, False)
    assert not XPEvent.objects.filter(person=member, source=f"path:{FORMA}").exists()
    assert "cota-0-a-certificacion" not in badges(member)


# --- credenciales: XP e insignias ---------------------------------------------------------------------------


def test_only_verified_credentials_give_xp(member, lead):
    cred = make_cred(member)
    assert xp(member) == 0
    creds.verify(cred, lead)
    assert xp(member) == 100
    assert "primer-trofeo" in badges(member)


@pytest.mark.parametrize(
    ("kind", "points"),
    [("completion", 100), ("certification", 500), ("license", 300), ("internal", 50)],
)
def test_xp_by_credential_kind(member, lead, kind, points):
    creds.verify(make_cred(member, kind=kind), lead)
    assert xp(member) == points


def test_rejecting_a_verified_credential_revokes_xp_and_badge(member, lead):
    cred = make_cred(member)
    creds.verify(cred, lead)
    creds.reject(cred, lead, "borroso")
    assert xp(member) == 0 and "primer-trofeo" not in badges(member)
    creds.verify(cred, lead)
    assert xp(member) == 100 and "primer-trofeo" in badges(member)


def test_editing_a_verified_credential_revokes_until_reverified(member, lead):
    cred = make_cred(member)
    creds.verify(cred, lead)
    creds.update_credential(cred, {"issuer": "Otro"})
    assert xp(member) == 0 and "primer-trofeo" not in badges(member)


def test_deleting_a_verified_credential_revokes_xp(member, lead):
    cred = make_cred(member)
    creds.verify(cred, lead)
    creds.delete_credential(cred)
    assert xp(member) == 0 and "primer-trofeo" not in badges(member)


def test_a_credential_marked_milestone_also_gives_milestone_xp(member, lead):
    resource = __import__("apps.catalog.models", fromlist=["Resource"]).Resource.objects.get(
        title="Learn Forma Site Design in 90 minutes"
    )
    cred = make_cred(member, resource=resource, path=forma())
    creds.verify(cred, lead)
    assert XPEvent.objects.filter(person=member, kind="milestone").count() == 1
    creds.reject(cred, lead, "no")
    assert not XPEvent.objects.filter(person=member, kind="milestone").exists()


def test_vendor_badges(member, lead):
    from apps.catalog.models import Resource

    resource = Resource.objects.get(title="Learn Forma Site Design in 90 minutes")
    creds.verify(make_cred(member, resource=resource), lead)
    assert {"iniciado-autodesk", "primer-trofeo"} <= badges(member)
    assert "triada-autodesk" not in badges(member)


def test_promoting_a_free_course_gives_the_promoter_xp_and_badge(member, lead):
    path = LearningPath.objects.get(slug="bentley-learn")
    cred = make_cred(
        member, title="STAAD", course_name_free="STAAD", path=path, platform=path.platform
    )
    creds.verify(cred, lead)
    creds.promote_free_course(cred, lead)
    assert XPEvent.objects.filter(person=member, kind="free_course_promoted", points=30).exists()
    assert "cartografo-de-cursos" in badges(member)


# --- reglas ----------------------------------------------------------------------------------------------------


def facts_for(person, today=None):
    return rules.Facts(person, today)


def test_rule_count_uses_event_kinds(member):
    game.award(member, "n:1", "note")
    rule = {"type": "count", "event": "note", "min": 2}
    assert not rules.check(rule, facts_for(member), lambda s: 0)
    game.award(member, "n:2", "note")
    assert rules.check(rule, facts_for(member), lambda s: 0)


def test_rule_path_complete_and_manual():
    assert rules.check({"type": "path_complete", "path": "x"}, None, lambda s: 100)
    assert not rules.check({"type": "path_complete", "path": "x"}, None, lambda s: 99)
    assert not rules.check({"type": "manual"}, None, lambda s: 100)


def test_rule_distinct_vendors(member, lead):
    from apps.catalog.models import Platform

    for slug in ("autodesk-learning", "esri-training", "microsoft-learn"):
        platform = Platform.objects.get(slug=slug)
        if platform.vendor_id is None:
            pytest.skip("la plataforma no tiene vendor en el seed")
        creds.verify(make_cred(member, title=slug, platform=platform), lead)
    rule = {"type": "distinct_vendors", "min": 3}
    assert rules.check(rule, facts_for(member), lambda s: 0)


def test_rule_requires_valid_turns_off_when_expired(member, lead):
    from apps.catalog.models import Platform

    platform = Platform.objects.get(slug="dgac-chile")
    cred = make_cred(
        member, kind="license", platform=platform, expires_on=date.today() + timedelta(days=30)
    )
    creds.verify(cred, lead)
    assert "alas-dgac" in badges(member)
    assert xp(member) == 300
    cred.expires_on = date.today() - timedelta(days=1)
    cred.save(update_fields=["expires_on"])
    game.evaluate(member)
    assert "alas-dgac" not in badges(member)
    assert xp(member) == 300  # el XP se conserva (GAMIFICACION)


def test_streak_helpers():
    today = date(2026, 10, 8)  # semana ISO 41
    weeks = {rules.week_key(today - timedelta(days=7 * n)) for n in range(4)}
    assert rules.streak_length(weeks, today) == 4
    assert rules.best_streak(weeks) == 4
    assert (
        rules.streak_length({rules.week_key(today - timedelta(days=7))}, today) == 1
    )  # esta semana aún vacía
    assert rules.streak_length({rules.week_key(today - timedelta(days=21))}, today) == 0
    gap = {rules.week_key(today), rules.week_key(today - timedelta(days=21))}
    assert rules.best_streak(gap) == 1


def test_streak_badge_and_weekly_xp(member):
    today = date(2026, 10, 8)
    for n in range(4):
        when = datetime.combine(today - timedelta(days=7 * n), datetime.min.time(), UTC)
        ev = XPEvent.objects.create(
            person=member, source=f"milestone:{900 + n}", kind="milestone", points=10
        )
        XPEvent.objects.filter(pk=ev.pk).update(created_at=when)
    game.evaluate(member, today)
    assert "racha-4" in badges(member) and "racha-12" not in badges(member)
    streak = XPEvent.objects.get(person=member, kind="streak")
    assert streak.points == 80 and streak.source == "streak:2026-W41"
    game.evaluate(member, today)
    assert XPEvent.objects.filter(person=member, kind="streak").count() == 1


def test_manual_badges_are_granted_by_leads_and_never_auto_revoked(member, lead):
    badge = Badge.objects.get(slug="gremio-unido")
    with pytest.raises(PermissionError):
        game.grant_manual(member, badge, member)
    with pytest.raises(ValueError):
        game.grant_manual(member, Badge.objects.get(slug="primera-luz"), lead)
    game.grant_manual(member, badge, lead)
    game.evaluate(member)
    assert "gremio-unido" in badges(member)


# --- títulos ---------------------------------------------------------------------------------------------------


def test_titles_follow_level_and_class(member):
    assert game.displayed_title(member).slug == "aprendiz-de-cota"
    game.award(member, "x:1", "manual", 600)  # nivel 4
    names = {t.slug for t in game.available_titles(member)}
    assert "dibujante-de-grilla" in names and "portador-del-jalon" not in names
    member.character_class = "cartographer"
    assert "portador-del-jalon" in {t.slug for t in game.available_titles(member)}


def test_a_chosen_title_must_still_be_available(member):
    game.award(member, "x:1", "manual", 600)
    member.selected_title = Title.objects.get(slug="dibujante-de-grilla")
    assert game.displayed_title(member).slug == "dibujante-de-grilla"
    member.selected_title = Title.objects.get(slug="leyenda-lev-101")
    assert game.displayed_title(member).slug != "leyenda-lev-101"


def test_special_titles_come_from_badges(member):
    progress.set_milestone(member, first_milestone(), True)
    assert "primera-luz" in {t.slug for t in game.available_titles(member)}


# --- semillas ----------------------------------------------------------------------------------------------------


def test_seed_is_idempotent_and_retires_what_leaves(settings):
    call_command("seed_catalog", verbosity=0)
    assert Badge.objects.filter(retired=False).count() == len(
        json.loads((settings.BASE_DIR / "seed" / "insignias.json").read_text("utf-8"))["badges"]
    )
    data = {
        "badges": [
            {
                "slug": "solo",
                "name": "S",
                "description": "d",
                "rarity": "common",
                "rule": {"type": "manual"},
            }
        ]
    }
    load_game(data, {"titles": []}, check_sprites=False)
    assert Badge.objects.get(slug="primera-luz").retired is True
    assert Badge.objects.get(slug="solo").retired is False


def test_every_seed_sprite_exists_and_the_seed_validates():
    import json
    from pathlib import Path

    from django.conf import settings

    seed = Path(settings.BASE_DIR) / "seed"
    b = json.loads((seed / "insignias.json").read_text(encoding="utf-8"))
    t = json.loads((seed / "titulos.json").read_text(encoding="utf-8"))
    assert validate_game(b, t) == []


def test_validation_catches_mistakes():
    bad = {
        "badges": [
            {
                "slug": "a",
                "name": "A",
                "description": "d",
                "rarity": "mythic",
                "rule": {"type": "count", "event": "x"},
            },
            {
                "slug": "a",
                "name": "A",
                "description": "d",
                "rarity": "common",
                "rule": {"type": "raro"},
            },
        ]
    }
    errors = "\n".join(
        validate_game(
            bad, {"titles": [{"slug": "t", "name": "T", "badge": "zzz"}]}, check_sprites=False
        )
    )
    assert "repetido" in errors and "rareza" in errors and "faltan" in errors
    assert "tipo de regla" in errors and "no existe" in errors
    with pytest.raises(SeedError):
        load_game(bad, {}, check_sprites=False)


# --- interfaz ----------------------------------------------------------------------------------------------------


def test_header_shows_level_and_title(client_for, member):
    html = client_for(member.login).get("/").content.decode()
    assert "NV 1" in html and "Aprendiz de Cota" in html


def test_celebrations_show_once_and_seen_clears_them(client_for, member):
    progress.set_milestone(member, first_milestone(), True)
    client = client_for(member.login)
    html = client.get("/").content.decode()
    assert "Nueva insignia" in html and "Primera Luz" in html
    ids = [b.pk for b in PersonBadge.objects.filter(person=member)]
    client.post("/juego/visto/", {"next": "/", "badge": ids})
    assert "Nueva insignia" not in client.get("/").content.decode()


def test_level_up_is_celebrated_once(client_for, member):
    game.award(member, "x:1", "manual", 150)
    client = client_for(member.login)
    assert "Subiste de nivel" in client.get("/").content.decode()
    client.post("/juego/visto/", {"next": "/", "level": 2})
    assert "Subiste de nivel" not in client.get("/").content.decode()


@pytest.mark.parametrize("target", ["//evil.com", "https://evil.com", "javascript:x"])
def test_seen_never_redirects_off_site(client_for, member, target):
    response = client_for(member.login).post("/juego/visto/", {"next": target})
    assert response["Location"] == "/"


def test_the_avatar_editor_unlocks_pieces_with_badges(member, lead):
    from apps.gamification import services

    assert services.unlocked_badges(member) == set()
    creds.verify(make_cred(member), lead)
    assert "primer-trofeo" in services.unlocked_badges(member)


def test_pending_people_get_no_game_context(client_for, make_person):
    pending = make_person("nuevo@lev.cl", status="pending")
    response = client_for(pending.login).get("/", follow=True)
    assert "NV " not in response.content.decode()


def test_badge_count_is_stable(member):
    assert PersonBadge.objects.filter(person=member).count() == 0
    assert Level.objects.exists()


def test_seen_only_marks_what_was_shown(client_for, member):
    progress.set_milestone(member, first_milestone(), True)
    shown = list(PersonBadge.objects.filter(person=member))
    later = PersonBadge.objects.create(person=member, badge=Badge.objects.get(slug="primera-nube"))
    client_for(member.login).post("/juego/visto/", {"next": "/", "badge": [b.pk for b in shown]})
    assert not PersonBadge.objects.filter(pk__in=[b.pk for b in shown], seen=False).exists()
    later.refresh_from_db()
    assert later.seen is False
