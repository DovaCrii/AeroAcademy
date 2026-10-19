from django.urls import path

from . import views

app_name = "cursos"

urlpatterns = [
    path("cursos/foto/<slug:slug>/<str:name>", views.course_photo, name="foto"),
    path("cursos/material/<slug:slug>/<str:name>", views.course_material, name="material"),
]
