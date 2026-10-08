from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("catalogo/", views.resources, name="resources"),
]
