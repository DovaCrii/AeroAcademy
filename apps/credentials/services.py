"""Credenciales: alta, edición, revisión y efectos sobre el avance. La lógica vive aquí; las vistas solo la llaman.

Reglas (docs/MODELO_DATOS.md):
- Al editar el archivo, las fechas o el emisor de una credencial verificada o rechazada, vuelve a `pending`.
- Al quedar `verified` con un recurso asociado, se marcan las misiones que ese recurso completa.
- Si deja de estar verificada (edición, rechazo o borrado), esas marcas se quitan.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Resource
from apps.gamification import game
from apps.notifications import services as notifications
from apps.paths.models import ExternalCourse, Level, Milestone
from apps.progress import services as progress

from . import files
from .models import Credential

# Cambiar cualquiera de estos campos (o el archivo) obliga a una nueva revisión.
EDITABLE = (
    "title", "issuer", "platform", "kind", "credential_id", "verify_url", "issued_on", "expires_on", "resource",
    "path", "visibility", "course_name_free", "course_url_free", "completed_on",
)  # fmt: skip
# Solo la visibilidad (y las habilidades) se cambian sin nueva revisión: todo lo demás define qué se verificó.
REVIEW_FIELDS = tuple(f for f in EDITABLE if f != "visibility")


# --- permisos --------------------------------------------------------------------------------------------------


def can_view(person, credential) -> bool:
    """Metadatos: la persona dueña, los responsables y, si está verificada y es del equipo, todos."""
    if credential.owner_id == person.pk or person.is_lead:
        return True
    return credential.is_verified and credential.visibility == Credential.Visibility.TEAM


def can_download(person, credential) -> bool:
    """El archivo contiene datos personales: solo la persona dueña y los responsables (D4)."""
    return credential.owner_id == person.pk or person.is_lead


def can_edit(person, credential) -> bool:
    return credential.owner_id == person.pk


def can_review(person) -> bool:
    return person.is_lead


# --- consultas ---------------------------------------------------------------------------------------------------


def for_owner(person):
    return Credential.objects.filter(owner=person).select_related("resource", "path", "platform")


def team_visible():
    return Credential.objects.filter(
        status=Credential.Status.VERIFIED, visibility=Credential.Visibility.TEAM
    ).select_related("owner", "resource", "platform")


def review_queue():
    return (
        Credential.objects.filter(status=Credential.Status.PENDING)
        .select_related("owner", "resource", "path", "platform")
        .order_by("created_at")
    )


_RANK = {Credential.Status.VERIFIED: 3, Credential.Status.PENDING: 2, Credential.Status.REJECTED: 1}


def states_by_resource(person):
    """resource_id → mejor estado de las credenciales de esa persona (verificada > en revisión > rechazada)."""
    best = {}
    for cred in Credential.objects.filter(owner=person, resource__isnull=False).only(
        "resource_id", "status", "id"
    ):
        current = best.get(cred.resource_id)
        if current is None or _RANK[cred.status] > _RANK[current[0]]:
            best[cred.resource_id] = (cred.status, cred.pk)
    return best


def free_courses_of(person, path):
    return Credential.objects.filter(owner=person, path=path, resource__isnull=True).exclude(
        course_name_free=""
    )


# --- escritura ----------------------------------------------------------------------------------------------------


def _set_fields(cred, data):
    for key in EDITABLE:
        if key in data:
            setattr(cred, key, data[key])


def _attach_file(cred, upload):
    kind, digest = files.validate_upload(upload)
    cred._ext = kind
    cred.file = upload
    cred.file_kind = kind
    cred.file_sha256 = digest


def create_credential(owner, data, upload):
    cred = Credential(owner=owner)
    _set_fields(cred, data)
    if not cred.title and cred.course_name_free:
        cred.title = cred.course_name_free
    _attach_file(cred, upload)
    try:
        with transaction.atomic():
            cred.save()
            if "skills" in data:
                cred.skills.set(data["skills"])
    except Exception:
        # Si algo falla después de guardar el archivo, no se deja un archivo sin fila.
        if cred.file and cred.file.name:
            cred.file.storage.delete(cred.file.name)
        raise
    _notify_review(cred)
    return cred


@transaction.atomic
def update_credential(cred, data, upload=None) -> bool:
    """Guarda cambios. Devuelve True si la credencial volvió a revisión."""
    needs_review = False
    for key in REVIEW_FIELDS:
        if key in data and getattr(cred, key) != data[key]:
            needs_review = True
    if upload is not None:
        needs_review = True
    was_verified = cred.is_verified
    _set_fields(cred, data)
    if upload is not None:
        old = cred.file.name
        _attach_file(cred, upload)
        cred.save()
        if old and old != cred.file.name:
            storage = cred.file.storage
            transaction.on_commit(lambda: storage.delete(old))  # solo si la transacción se confirma
    if needs_review and cred.status != Credential.Status.PENDING:
        _back_to_pending(cred, save=False)
    cred.save()
    if "skills" in data:
        cred.skills.set(data["skills"])
    if needs_review and cred.status == Credential.Status.PENDING:
        _notify_review(cred)
    if was_verified and cred.status != Credential.Status.VERIFIED:
        _unapply(cred)
    game.refresh(cred.owner)  # lo derivado (XP, insignias, marcas) se recalcula siempre
    return needs_review and cred.status == Credential.Status.PENDING


def _notify_review(cred):
    notifications.notify_leads(
        "credential_submitted",
        f"{cred.owner.name} envió una credencial a revisión",
        cred.display_title,
        url="/certificados/revisar/",
        key=f"cred-review:{cred.pk}:{cred.updated_at.timestamp():.6f}",
        exclude=cred.owner,
    )


def _back_to_pending(cred, *, save=True):
    cred.status = Credential.Status.PENDING
    cred.reviewed_by = None
    cred.reviewed_at = None
    cred.review_comment = ""
    if save:
        cred.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"]
        )


def version_of(cred) -> str:
    """Huella de lo que vio quien revisa: si la credencial cambia después, la revisión se rechaza."""
    return cred.updated_at.isoformat()


def _lock_for_review(cred, by, version):
    """Bloquea la fila, recarga su estado y comprueba permisos y que no haya cambiado desde que se abrió."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede revisar credenciales.")
    Credential.objects.select_for_update().filter(pk=cred.pk).first()
    cred.refresh_from_db()
    if cred.owner_id == by.pk and not by.is_admin:
        # D26: un responsable no revisa lo suyo; el administrador sí (el equipo puede ser de una sola persona).
        raise PermissionError("No puedes revisar tus propias credenciales.")
    if version is not None and version != version_of(cred):
        raise ValueError("La credencial cambió mientras la revisabas. Ábrela de nuevo.")


@transaction.atomic
def verify(cred, by, comment="", *, version=None):
    _lock_for_review(cred, by, version)
    if cred.is_verified:
        raise ValueError("La credencial ya está verificada.")
    cred.status = Credential.Status.VERIFIED
    cred.reviewed_by, cred.reviewed_at, cred.review_comment = by, timezone.now(), comment.strip()
    cred.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"]
    )
    _apply_verified(cred)
    game.refresh(cred.owner)
    notifications.notify(
        cred.owner,
        "credential_verified",
        f"Tu credencial «{cred.display_title}» fue verificada",
        url=f"/certificados/{cred.pk}/",
        key=f"cred-verified:{cred.pk}:{cred.reviewed_at.timestamp():.6f}",
    )
    return cred


@transaction.atomic
def reject(cred, by, comment, *, version=None):
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede revisar credenciales.")
    if not (comment or "").strip():
        raise ValueError("Al rechazar hay que explicar el motivo.")
    _lock_for_review(cred, by, version)
    if cred.status == Credential.Status.REJECTED:
        raise ValueError("La credencial ya está rechazada.")
    was_verified = cred.is_verified
    cred.status = Credential.Status.REJECTED
    cred.reviewed_by, cred.reviewed_at, cred.review_comment = by, timezone.now(), comment.strip()
    cred.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"]
    )
    if was_verified:
        _unapply(cred)
        game.refresh(cred.owner)
    notifications.notify(
        cred.owner,
        "credential_rejected",
        f"Tu credencial «{cred.display_title}» fue rechazada",
        cred.review_comment,
        url=f"/certificados/{cred.pk}/",
        key=f"cred-rejected:{cred.pk}:{cred.reviewed_at.timestamp():.6f}",
    )
    return cred


@transaction.atomic
def delete_credential(cred):
    """Borra la credencial y las marcas que respaldaba. El archivo lo borra la señal `post_delete`."""
    owner, resource_id = cred.owner, cred.resource_id
    was_verified = cred.is_verified
    cred.delete()  # las marcas de misiones se van en cascada
    if was_verified and resource_id:
        _reapply_others(owner, resource_id)
    if was_verified:
        game.refresh(owner)


def _apply_verified(cred):
    """Marca las misiones que completa el recurso de esta credencial."""
    if not cred.resource_id:
        return
    for milestone in Milestone.objects.filter(
        completed_by_resource_id=cred.resource_id, retired=False
    ):
        progress.set_milestone(cred.owner, milestone, True, credential=cred)


def _unapply(cred):
    """Quita las marcas que respaldaba esta credencial; si otra verificada respalda lo mismo, vuelven a su nombre."""
    cred.checks.all().delete()
    if cred.resource_id:
        _reapply_others(cred.owner, cred.resource_id, exclude=cred.pk)


def _reapply_others(owner, resource_id, exclude=None):
    others = Credential.objects.filter(
        owner=owner, resource_id=resource_id, status=Credential.Status.VERIFIED
    )
    if exclude:
        others = others.exclude(pk=exclude)
    for other in others:
        _apply_verified(other)


@transaction.atomic
def promote_free_course(cred, by):
    """Un responsable suma al catálogo un curso libre aprobado: queda en el capítulo de cursos libres de la ruta."""
    if not by.is_lead:
        raise PermissionError("Solo un responsable puede promover cursos.")
    if cred.resource_id or not cred.course_name_free or not cred.path_id:
        raise ValueError("Esta credencial no es un curso libre.")
    if not cred.is_verified:
        raise ValueError("Solo se promueven cursos con el certificado verificado.")
    path = cred.path
    if not path.allow_free_courses or not path.platform_id:
        raise ValueError("Esta ruta no admite cursos libres.")
    level = Level.objects.filter(path=path, is_free_courses=True).first()
    if level is None:
        raise ValueError("La ruta no tiene capítulo de cursos libres.")

    resource, _ = Resource.objects.get_or_create(
        platform=path.platform,
        title=cred.course_name_free,
        defaults={
            "url": cred.course_url_free,
            "kind": Resource.Kind.COURSE,
            "grants_completion_certificate": True,
            "proposed_by": cred.owner,
        },
    )
    taken = {
        k
        for k in ExternalCourse.objects.filter(path=path, key__startswith="lib-c").values_list(
            "key", flat=True
        )
    }
    number = 0
    while f"lib-c{number}" in taken:
        number += 1
    ExternalCourse.objects.get_or_create(
        path=path,
        resource=resource,
        defaults={
            "key": f"lib-c{number}",
            "level": level,
            "order": number,
            "reward": ExternalCourse.Reward.TROPHY,
            "is_required": False,
        },
    )
    cred.resource = resource
    cred.save(update_fields=["resource", "updated_at"])
    if cred.is_verified:
        _apply_verified(cred)
    game.award(
        cred.owner, f"free_course:{resource.pk}", "free_course_promoted", label=resource.title
    )
    game.refresh(cred.owner)
    return resource


def visible_filter(person):
    """Q para listar credenciales que `person` puede ver (usado por la lista del equipo)."""
    if person.is_lead:
        return Q()
    return Q(owner=person) | Q(
        status=Credential.Status.VERIFIED, visibility=Credential.Visibility.TEAM
    )
