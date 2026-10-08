from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("avisos/", views.inbox, name="inbox"),
    path("avisos/leer/", views.read, name="read_all"),
    path("avisos/<int:pk>/leer/", views.read, name="read"),
]
