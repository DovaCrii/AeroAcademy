from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.functional import cached_property

from apps.core.models import TimeStampedModel


class PersonStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de aprobación"
    APPROVED = "approved", "Aprobada"
    SUSPENDED = "suspended", "Suspendida"


class CharacterClass(models.TextChoices):
    ARCHITECT = "architect", "Arquitecto-Constructor"
    ENGINEER = "engineer", "Calculista"
    CARTOGRAPHER = "cartographer", "Cartógrafo"
    ARTIFICER = "artificer", "Artífice"
    PILOT = "pilot", "Piloto de Nubes"


class PersonManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, login, password=None, **extra):
        login = (login or "").strip().lower()
        if not login:
            raise ValueError("La persona necesita un login.")
        person = self.model(login=login, **extra)
        if password:
            person.set_password(password)
        else:
            person.set_unusable_password()
        person.save(using=self._db)
        return person

    def create_superuser(self, login, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("status", PersonStatus.APPROVED)
        return self.create_user(login, password, **extra)


class Person(TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    """Persona del equipo. La identidad es el login de Tailscale (D2): no hay contraseña."""

    login = models.CharField("login de Tailscale", max_length=254, unique=True)
    display_name = models.CharField("nombre", max_length=150, blank=True)
    avatar_url = models.URLField("foto", max_length=500, blank=True)
    role_title = models.CharField("cargo", max_length=120, blank=True)
    # Texto libre por ahora; pasa a M2M con catalog.Discipline en el Bloque 2.
    discipline = models.CharField("disciplina", max_length=40, blank=True)

    is_active = models.BooleanField("activa", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)

    status = models.CharField(
        "estado", max_length=12, choices=PersonStatus.choices, default=PersonStatus.PENDING
    )
    approved_by = models.ForeignKey(
        "self",
        verbose_name="aprobada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approvals",
    )
    approved_at = models.DateTimeField("aprobada el", null=True, blank=True)

    # Hoja de personaje (Bloque 14). El título elegido y los accesorios llegan con gamification.
    headline = models.CharField("titular profesional", max_length=90, blank=True)
    bio = models.CharField("bio", max_length=600, blank=True)
    links = models.JSONField("enlaces", default=dict, blank=True)
    character_class = models.CharField(
        "clase", max_length=14, choices=CharacterClass.choices, blank=True
    )
    avatar_config = models.JSONField("avatar", default=dict, blank=True)
    show_game_view = models.BooleanField("vista de juego", default=True)

    objects = PersonManager()

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "persona"
        verbose_name_plural = "personas"
        ordering = ["display_name", "login"]

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.display_name or self.login.split("@")[0]

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    @property
    def is_approved(self):
        return self.status == PersonStatus.APPROVED

    @cached_property
    def role(self):
        """`admin` > `lead` > `member`. El admin es superusuario; el lead, el grupo `lead`."""
        if self.is_superuser:
            return "admin"
        if self.groups.filter(name="lead").exists():
            return "lead"
        return "member"

    @property
    def is_lead(self):
        return self.role in {"lead", "admin"}

    @property
    def is_admin(self):
        return self.role == "admin"
