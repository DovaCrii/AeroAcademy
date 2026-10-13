from django.urls import path

from . import views

app_name = "paths"

urlpatterns = [
    path("rutas/", views.index, name="index"),
    path("rutas/mapa/", views.metro_map, name="map"),
    path("rutas/<slug:slug>/", views.detail, name="detail"),
]
