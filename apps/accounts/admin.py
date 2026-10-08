from django.contrib import admin, messages

from . import services
from .models import Person, PersonStatus


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "login", "status", "role_label", "discipline", "created_at")
    list_filter = ("status", "character_class")
    search_fields = ("login", "display_name")
    ordering = ("status", "-created_at")
    # El rol y el acceso al admin se cambian solo con las acciones (pasan por services).
    readonly_fields = (
        "login",
        "is_superuser",
        "is_staff",
        "groups",
        "approved_by",
        "approved_at",
        "last_login",
        "created_at",
        "updated_at",
    )
    exclude = ("password", "user_permissions")
    actions = ["approve_people", "suspend_people", "make_member", "make_lead", "make_admin"]

    @admin.display(description="rol")
    def role_label(self, person):
        return person.role

    def has_add_permission(self, request):
        return False  # las personas se crean al entrar por Tailscale

    @admin.action(description="Aprobar personas seleccionadas")
    def approve_people(self, request, queryset):
        for person in queryset.exclude(status=PersonStatus.APPROVED):
            services.approve(person, by=request.user)
        self.message_user(request, "Personas aprobadas.", messages.SUCCESS)

    @admin.action(description="Suspender personas seleccionadas")
    def suspend_people(self, request, queryset):
        for person in queryset.exclude(pk=request.user.pk):
            services.suspend(person)
        self.message_user(request, "Personas suspendidas (tú no).", messages.SUCCESS)

    def _set_role(self, request, queryset, role):
        for person in queryset.exclude(pk=request.user.pk):
            services.set_role(person, role)
        self.message_user(request, f"Rol «{role}» asignado (tu propio rol no cambia).")

    @admin.action(description="Asignar rol: member")
    def make_member(self, request, queryset):
        self._set_role(request, queryset, "member")

    @admin.action(description="Asignar rol: lead")
    def make_lead(self, request, queryset):
        self._set_role(request, queryset, "lead")

    @admin.action(description="Asignar rol: admin")
    def make_admin(self, request, queryset):
        self._set_role(request, queryset, "admin")
