from django.db import models

from apps.core.models import TimeStampedModel


class SharedCheck(TimeStampedModel):
    """Casilla compartida del kit o del plan de implementación: la marca todo el equipo, una sola vez."""

    item = models.OneToOneField(
        "paths.SharedItem", on_delete=models.CASCADE, related_name="shared_check"
    )
    checked_by = models.ForeignKey(
        "accounts.Person", null=True, on_delete=models.SET_NULL, related_name="shared_checks"
    )

    class Meta:
        verbose_name = "casilla compartida marcada"
        verbose_name_plural = "casillas compartidas marcadas"

    def __str__(self):
        return f"{self.item.key} ✔"


class TeamMember(TimeStampedModel):
    """Datos de incorporación de una persona del equipo que no viven en `accounts.Person`.

    Tailscale no se puede consultar desde la academia: quien responsable invita a la persona en su consola
    y deja aquí la marca manual `tailscale_invited`.
    """

    person = models.OneToOneField(
        "accounts.Person", on_delete=models.CASCADE, related_name="team_member"
    )
    tailscale_invited = models.BooleanField("invitada a Tailscale", default=False)
    invited_at = models.DateTimeField("invitada el", null=True, blank=True)
    invited_by = models.ForeignKey(
        "accounts.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "incorporación al equipo"
        verbose_name_plural = "incorporaciones al equipo"

    def __str__(self):
        return f"{self.person_id} · invitada={self.tailscale_invited}"
