from django.urls import path

from . import views

app_name = "gamification"

urlpatterns = [
    path("perfil/", views.my_sheet, name="my_sheet"),
    path("perfil/editar/", views.edit_sheet, name="edit_sheet"),
    path("personas/", views.directory, name="directory"),
    path("personas/<int:pk>/", views.sheet, name="sheet"),
    path("juego/visto/", views.seen, name="seen"),
    path("perfil/avatar/", views.avatar_editor, name="avatar_editor"),
    path("perfil/avatar/vista/", views.avatar_preview, name="avatar_preview"),
]
