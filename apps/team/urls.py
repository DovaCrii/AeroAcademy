from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("equipo/", views.board, name="board"),
    path("equipo/matriz/", views.matrix, name="matrix"),
    path("equipo/kit/<slug:slug>/", views.kit, name="kit"),
    path("equipo/kit/<slug:slug>/<str:key>/", views.toggle, name="toggle"),
]
