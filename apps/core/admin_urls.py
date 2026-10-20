"""Rutas del Centro de administración (D42). `core/urls.py` las suma a las de `core`: los nombres son `core:admin_*`.
Toda ruta nueva empieza por /administracion/ (que además está en PUBLIC_BLOCKED_PREFIXES)."""

from django.urls import path

from . import admin_views as views

urlpatterns = [
    path("administracion/", views.center, name="admin_center"),
    path("administracion/cuentas/", views.accounts, name="admin_accounts"),
    path("administracion/cuentas/<int:pk>/aprobar/", views.account_approve, name="admin_approve"),
    path("administracion/cuentas/<int:pk>/rechazar/", views.account_reject, name="admin_reject"),
    path("administracion/cuentas/<int:pk>/rol/", views.account_role, name="admin_role"),
    path("administracion/cuentas/<int:pk>/suspender/", views.account_suspend, name="admin_suspend"),
    path(
        "administracion/cuentas/<int:pk>/reactivar/",
        views.account_reactivate,
        name="admin_reactivate",
    ),
    path("administracion/cuentas/<int:pk>/enlace/", views.account_link, name="admin_link"),
    path("administracion/enlace-equipo/", views.team_link_create, name="admin_team_link"),
    path(
        "administracion/enlace-equipo/revocar/",
        views.team_link_revoke,
        name="admin_team_link_revoke",
    ),
    path("administracion/bitacora/", views.log, name="admin_log"),
]
