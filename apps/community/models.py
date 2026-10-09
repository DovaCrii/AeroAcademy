from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel

NOTE_MAX = 1000


class Note(TimeStampedModel):
    """Nota del equipo sobre una ruta, un capítulo o un recurso; las respuestas cuelgan de otra nota."""

    class Type(models.TextChoices):
        WORKS = "works", "Funciona"
        FAILS = "fails", "No funciona"
        TIP = "tip", "Recomendación"
        ASK = "ask", "Pregunta"
        REPLY = "reply", "Respuesta"

    author = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="notes")
    path = models.ForeignKey("paths.LearningPath", on_delete=models.CASCADE, related_name="notes")
    level = models.ForeignKey(
        "paths.Level", null=True, blank=True, on_delete=models.SET_NULL, related_name="notes"
    )
    resource = models.ForeignKey(
        "catalog.Resource", null=True, blank=True, on_delete=models.SET_NULL, related_name="notes"
    )
    type = models.CharField("tipo", max_length=6, choices=Type.choices)
    text = models.CharField("texto", max_length=NOTE_MAX)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    is_deleted = models.BooleanField("borrada", default=False)
    is_hidden = models.BooleanField("oculta por moderación", default=False)
    legacy_id = models.CharField(max_length=40, blank=True)  # id en el prototipo (import_legacy)

    class Meta:
        verbose_name = "nota"
        verbose_name_plural = "notas"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["path", "level", "is_deleted"])]
        constraints = [
            models.UniqueConstraint(
                fields=["legacy_id"], condition=~Q(legacy_id=""), name="uniq_note_legacy_id"
            )
        ]

    def __str__(self):
        return f"{self.get_type_display()} · {self.author}"


THREAD_TITLE_MAX = 150
BODY_MAX = 5000


class Category(TimeStampedModel):
    slug = models.SlugField(unique=True)
    name = models.CharField("nombre", max_length=80)
    description = models.CharField("descripción", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    retired = models.BooleanField("retirada", default=False)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Thread(TimeStampedModel):
    """Hilo del foro: una conversación (`discussion`) o una consulta con respuesta aceptada (`question`)."""

    class Kind(models.TextChoices):
        DISCUSSION = "discussion", "Conversación"
        QUESTION = "question", "Consulta"

    author = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="threads")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="threads")
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.QUESTION)
    title = models.CharField("título", max_length=THREAD_TITLE_MAX)
    body = models.TextField("detalle", max_length=BODY_MAX)
    disciplines = models.ManyToManyField("catalog.Discipline", blank=True, related_name="threads")
    accepted_post = models.ForeignKey(
        "Post", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_closed = models.BooleanField("cerrado", default=False)
    is_pinned = models.BooleanField("fijado", default=False)
    is_hidden = models.BooleanField("oculto por moderación", default=False)
    hidden_reason = models.CharField("motivo", max_length=300, blank=True)
    last_activity_at = models.DateTimeField("última actividad", auto_now_add=True)

    class Meta:
        verbose_name = "hilo"
        verbose_name_plural = "hilos"
        ordering = ["-is_pinned", "-last_activity_at", "-id"]
        indexes = [models.Index(fields=["category", "-last_activity_at"])]

    def __str__(self):
        return self.title

    @property
    def is_answered(self):
        return self.accepted_post_id is not None


class Post(TimeStampedModel):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="posts")
    body = models.TextField("mensaje", max_length=BODY_MAX)
    is_deleted = models.BooleanField("borrado", default=False)
    is_hidden = models.BooleanField("oculto por moderación", default=False)
    hidden_reason = models.CharField("motivo", max_length=300, blank=True)

    class Meta:
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.author} en {self.thread_id}"


class ModerationLog(models.Model):
    """Bitácora de moderación: quién hizo qué, sobre qué y por qué. Solo la ven los responsables."""

    actor = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="moderation_actions"
    )
    action = models.CharField("acción", max_length=30)
    object_type = models.CharField(max_length=20)
    object_id = models.PositiveIntegerField()
    summary = models.CharField("detalle", max_length=200, blank=True)
    reason = models.CharField("motivo", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de moderación"
        verbose_name_plural = "bitácora de moderación"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} {self.object_type}:{self.object_id}"


class Report(TimeStampedModel):
    """Reporte de un mensaje del foro o de una nota, que llega a la cola de los responsables."""

    class Status(models.TextChoices):
        OPEN = "open", "Abierto"
        HIDDEN = "hidden", "Ocultado"
        DISMISSED = "dismissed", "Descartado"

    reporter = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="reports_made"
    )
    target_type = models.CharField(max_length=10)  # "post" | "note"
    target_id = models.PositiveIntegerField()
    reason = models.CharField("motivo", max_length=300)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(
        "accounts.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.target_type}:{self.target_id} ({self.status})"


class Reaction(TimeStampedModel):
    """Una reacción de una persona a un hilo o a un mensaje (una por persona y tipo; se alterna)."""

    class Kind(models.TextChoices):
        USEFUL = "useful", "Útil"
        IDEA = "idea", "Buena idea"
        TESTED = "tested", "Lo probé"
        HELPED = "helped", "Me sirvió"

    EMOJI = {"useful": "👍", "idea": "💡", "tested": "✅", "helped": "🎯"}

    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="forum_reactions"
    )
    thread = models.ForeignKey(
        Thread, null=True, blank=True, on_delete=models.CASCADE, related_name="reactions"
    )
    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.CASCADE, related_name="reactions"
    )
    kind = models.CharField("reacción", max_length=8, choices=Kind.choices)

    class Meta:
        verbose_name = "reacción"
        verbose_name_plural = "reacciones"
        constraints = [
            models.UniqueConstraint(
                fields=["person", "thread", "kind"],
                condition=Q(thread__isnull=False),
                name="uniq_reaction_thread",
            ),
            models.UniqueConstraint(
                fields=["person", "post", "kind"],
                condition=Q(post__isnull=False),
                name="uniq_reaction_post",
            ),
            models.CheckConstraint(
                condition=Q(thread__isnull=False, post__isnull=True)
                | Q(thread__isnull=True, post__isnull=False),
                name="reaction_one_target",
            ),
        ]

    def __str__(self):
        return f"{self.kind} · {self.person}"


class PollOption(models.Model):
    """Opción de la encuesta rápida de un hilo (2 a 6)."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="poll_options")
    text = models.CharField("opción", max_length=80)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "opción de encuesta"
        verbose_name_plural = "opciones de encuesta"
        ordering = ["position", "id"]

    def __str__(self):
        return self.text


class PollVote(TimeStampedModel):
    """Voto de una persona en la encuesta de un hilo: uno por persona, cambiable mientras esté abierto."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="poll_votes")
    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="poll_votes"
    )
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes")

    class Meta:
        verbose_name = "voto"
        verbose_name_plural = "votos"
        constraints = [
            models.UniqueConstraint(fields=["thread", "person"], name="uniq_poll_vote_person")
        ]

    def __str__(self):
        return f"{self.person} → {self.option_id}"
