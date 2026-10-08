from django.urls import path

from . import views

app_name = "gamification"

urlpatterns = [
    path("juego/visto/", views.seen, name="seen"),
    path("perfil/avatar/", views.avatar_editor, name="avatar_editor"),
    path("perfil/avatar/vista/", views.avatar_preview, name="avatar_preview"),
]
