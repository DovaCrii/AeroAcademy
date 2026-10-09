from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("equipo/", views.board, name="board"),
    path("equipo/matriz/", views.matrix, name="matrix"),
    path("equipo/personas/", views.people, name="people"),
    path("equipo/personas/agregar/", views.people_add, name="people_add"),
    path("equipo/personas/<int:pk>/", views.person_update, name="person_update"),
    path("equipo/personas/<int:pk>/invitada/", views.person_invited, name="person_invited"),
    path("equipo/kit/<slug:slug>/", views.kit, name="kit"),
    path("equipo/kit/<slug:slug>/<str:key>/", views.toggle, name="toggle"),
]
