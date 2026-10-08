"""Importa los datos del prototipo (`ruta.db` de forma-ruta) a AeroAcademy. Idempotente: correrlo dos veces no duplica.

Tablas del prototipo: `people`, `progress` (JSON por persona), `notes` y `shared`. Ver docs/ARQUITECTURA.md.
Las personas importadas quedan **aprobadas** (ya participaban del equipo); las notas se importan sin XP ni avisos,
con su fecha original, para no regalar puntos ni llenar la campana.
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from django.db import transaction

from apps.accounts import services as accounts
from apps.accounts.models import Person, PersonStatus
from apps.community.models import Note
from apps.gamification import game
from apps.paths.models import (
    LearningPath,
    Level,
    LevelResource,
    Milestone,
    QuizQuestion,
    SharedItem,
)
from apps.progress import services as progress
from apps.progress.models import MilestoneCheck, PathGoal, QuizAnswer
from apps.team.models import SharedCheck

NOTE_TYPES = {"works", "fails", "tip", "ask"}
TEXT_MAX = 1000


class LegacyError(Exception):
    pass


def _ts(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _rows(con, table):
    try:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table}")]  # noqa: S608  (tabla fija, no del usuario)
    except sqlite3.Error:
        return []


def import_legacy(db_path, *, path_slug="forma-revit", refresh=True):
    """Devuelve un resumen con lo creado y lo omitido. Todo ocurre en una transacción."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise LegacyError(f"No existe la base del prototipo: {db_path}")
    path = LearningPath.objects.filter(slug=path_slug).first()
    if path is None:
        raise LegacyError(f"No existe la ruta «{path_slug}». Corre primero `seed_catalog`.")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        people, prog, notes, shared = (
            _rows(con, t) for t in ("people", "progress", "notes", "shared")
        )
    finally:
        con.close()

    summary = {
        "people": 0, "checks": 0, "quiz": 0, "goals": 0, "notes": 0, "shared": 0,
        "skipped": [],
    }  # fmt: skip
    with transaction.atomic():
        by_login = _import_people(people, summary)
        _import_progress(prog, path, by_login, summary)
        _import_notes(notes, path, by_login, summary)
        _import_shared(shared, path, by_login, summary)
        if refresh:
            for person in by_login.values():
                game.refresh(person)
    return summary


def _person_for(login, by_login, summary):
    login = accounts.normalize_login(login)
    if not login:
        return None
    if login not in by_login:
        person = Person.objects.filter(login=login).first()
        if person is None:
            person = Person.objects.create_user(login=login, status=PersonStatus.APPROVED)
            accounts.init_new_person(person)
            summary["people"] += 1
        by_login[login] = person
    return by_login[login]


def _import_people(rows, summary):
    by_login = {}
    for row in rows:
        person = _person_for(row.get("id"), by_login, summary)
        if person is None:
            continue
        name = (row.get("name") or "").strip()[:150]
        pic = accounts.clean_avatar_url(row.get("pic") or "")
        changed = []
        if name and not person.display_name:
            person.display_name = name
            changed.append("display_name")
        if pic and not person.avatar_url:
            person.avatar_url = pic
            changed.append("avatar_url")
        if changed:
            person.save(update_fields=[*changed, "updated_at"])
    return by_login


def _import_progress(rows, path, by_login, summary):
    milestones = {m.key: m for m in Milestone.objects.filter(path=path, retired=False)}
    questions = {q.key: q for q in QuizQuestion.objects.filter(path=path, retired=False)}
    for row in rows:
        person = _person_for(row.get("id"), by_login, summary)
        if person is None:
            continue
        try:
            data = json.loads(row.get("data") or "{}")
        except ValueError:
            summary["skipped"].append(f"avance de {row.get('id')}: JSON inválido")
            continue
        for key, done in (data.get("checks") or {}).items():
            milestone = milestones.get(key)
            if not done:
                continue
            if milestone is None:
                summary["skipped"].append(f"misión desconocida «{key}»")
                continue
            _, created = MilestoneCheck.objects.get_or_create(person=person, milestone=milestone)
            summary["checks"] += int(created)
        for key, choice in (data.get("quiz") or {}).items():
            question = questions.get(key)
            if (
                question is None
                or not isinstance(choice, int)
                or not 0 <= choice < len(question.options)
            ):
                summary["skipped"].append(f"respuesta desconocida «{key}»")
                continue
            _, created = QuizAnswer.objects.get_or_create(
                person=person, question=question, defaults={"selected_index": choice}
            )
            summary["quiz"] += int(created)
        goal = str(data.get("certGoal") or "").strip()
        if goal and not PathGoal.objects.filter(person=person, path=path).exists():
            try:
                progress.set_goal(person, path, goal)
                summary["goals"] += 1
            except ValueError:
                summary["skipped"].append(f"meta desconocida «{goal[:40]}»")


def _resource_for(level, index):
    if level is None or not isinstance(index, int) or index < 0:
        return None
    links = list(
        LevelResource.objects.filter(level=level).order_by("order").select_related("resource")
    )
    return links[index].resource if index < len(links) else None


def _import_notes(rows, path, by_login, summary):
    levels = {lv.code.lower(): lv for lv in Level.objects.filter(path=path)}
    imported = {n.legacy_id: n for n in Note.objects.filter(path=path).exclude(legacy_id="")}
    ordered = sorted(
        rows, key=lambda r: (r.get("parent") is not None, r.get("ts") or 0)
    )  # padres primero
    for row in ordered:
        legacy_id = str(row.get("id") or "")
        text = (row.get("text") or "").strip()[:TEXT_MAX]
        if not legacy_id or not text:
            summary["skipped"].append("nota vacía o sin id")
            continue
        if legacy_id in imported:
            continue
        author = _person_for(row.get("author"), by_login, summary)
        if author is None:
            summary["skipped"].append(f"nota {legacy_id[:8]}: sin autor")
            continue
        parent = None
        if row.get("parent"):
            parent = imported.get(str(row["parent"]))
            if parent is None:
                summary["skipped"].append(f"respuesta {legacy_id[:8]}: su nota ya no existe")
                continue
        level = parent.level if parent else levels.get(str(row.get("lv") or "").lower())
        note_type = (
            "reply" if parent else (row.get("type") if row.get("type") in NOTE_TYPES else "tip")
        )
        note = Note.objects.create(
            author=author,
            path=path,
            level=level,
            resource=parent.resource if parent else _resource_for(level, row.get("res")),
            type=note_type,
            text=text,
            parent=parent,
            legacy_id=legacy_id,
        )
        when = _ts(row.get("ts"))
        if when:
            Note.objects.filter(pk=note.pk).update(created_at=when)
        imported[legacy_id] = note
        summary["notes"] += 1


def _import_shared(rows, path, by_login, summary):
    items = {i.key: i for i in SharedItem.objects.filter(path=path)}
    for row in rows:
        item = items.get(row.get("key"))
        if item is None:
            summary["skipped"].append(f"casilla desconocida «{row.get('key')}»")
            continue
        who = _person_for(row.get("by"), by_login, summary)
        check, created = SharedCheck.objects.get_or_create(item=item, defaults={"checked_by": who})
        if created:
            when = _ts(row.get("ts"))
            if when:
                SharedCheck.objects.filter(pk=check.pk).update(created_at=when)
            summary["shared"] += 1
