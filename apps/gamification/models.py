from django.db import models

from apps.core.models import TimeStampedModel


class XPEvent(TimeStampedModel):
    """Un punto de experiencia ganado. Único por (persona, origen): repetir la acción no duplica XP."""

    person = models.ForeignKey(
        "accounts.Person", on_delete=models.CASCADE, related_name="xp_events"
    )
    source = models.CharField(
        "origen", max_length=120
    )  # ej.: milestone:12, credential:7, streak:2026-W41
    kind = models.CharField(
        "tipo", max_length=24
    )  # milestone, quiz, chapter, path, credential, ...
    points = models.PositiveIntegerField("puntos", default=0)
    label = models.CharField("detalle", max_length=200, blank=True)

    class Meta:
        verbose_name = "evento de XP"
        verbose_name_plural = "eventos de XP"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["person", "source"], name="uniq_xp_person_source")
        ]
        indexes = [models.Index(fields=["person", "kind"])]

    def __str__(self):
        return f"{self.person} +{self.points} ({self.source})"


class Badge(TimeStampedModel):
    class Rarity(models.TextChoices):
        COMMON = "common", "Común"
        RARE = "rare", "Rara"
        EPIC = "epic", "Épica"
        LEGENDARY = "legendary", "Legendaria"

    slug = models.SlugField(unique=True)
    name = models.CharField("nombre", max_length=80)
    description = models.CharField("descripción", max_length=200)
    rarity = models.CharField("rareza", max_length=10, choices=Rarity.choices)
    sprite = models.CharField(max_length=80, blank=True)
    rule = models.JSONField("regla", default=dict)
    order = models.PositiveSmallIntegerField(default=0)
    retired = models.BooleanField("retirada", default=False)  # D7: no se borra, se retira

    class Meta:
        verbose_name = "insignia"
        verbose_name_plural = "insignias"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class PersonBadge(TimeStampedModel):
    person = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    earned_at = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField("avisada", default=False)
    granted_by = models.ForeignKey(
        "accounts.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )  # solo las insignias `manual`

    class Meta:
        verbose_name = "insignia ganada"
        verbose_name_plural = "insignias ganadas"
        ordering = ["-earned_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["person", "badge"], name="uniq_person_badge")
        ]

    def __str__(self):
        return f"{self.person} · {self.badge}"


class Title(TimeStampedModel):
    slug = models.SlugField(unique=True)
    name = models.CharField("nombre", max_length=80)
    min_level = models.PositiveSmallIntegerField("nivel mínimo", default=0)
    character_class = models.CharField("clase", max_length=14, blank=True)
    badge = models.ForeignKey(
        Badge, null=True, blank=True, on_delete=models.SET_NULL, related_name="titles"
    )  # título especial: lo da una insignia
    order = models.PositiveSmallIntegerField(default=0)
    retired = models.BooleanField("retirado", default=False)

    class Meta:
        verbose_name = "título"
        verbose_name_plural = "títulos"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class PlayerState(TimeStampedModel):
    """Lo último que se le mostró a la persona, para celebrar una sola vez."""

    person = models.OneToOneField(
        "accounts.Person", on_delete=models.CASCADE, related_name="player_state"
    )
    celebrated_level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "estado de juego"
        verbose_name_plural = "estados de juego"
