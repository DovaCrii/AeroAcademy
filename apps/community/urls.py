from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("rutas/<slug:slug>/notas/", views.path_notes, name="path_notes"),
    path("notas/<int:pk>/responder/", views.reply, name="reply"),
    path("notas/<int:pk>/eliminar/", views.delete, name="delete"),
]
