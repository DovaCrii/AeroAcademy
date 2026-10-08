from django.contrib import admin

from .models import Credential


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "kind", "status", "issued_on", "expires_on", "visibility")
    list_filter = ("status", "kind", "visibility", "platform")
    search_fields = ("title", "issuer", "credential_id", "owner__login")
    raw_id_fields = ("owner", "reviewed_by", "resource", "path")
    filter_horizontal = ("skills",)
    # El archivo se descarga solo por la vista con permisos; aquí no se muestra su ruta.
    exclude = ("file",)
    readonly_fields = ("file_sha256", "file_kind", "created_at", "updated_at")
