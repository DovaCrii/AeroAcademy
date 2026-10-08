from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("teo/", views.page, name="page"),
    path("teo/ask/", views.ask, name="ask"),
    path("teo/resumir/<int:pk>/", views.summarize, name="summarize"),
    path("ayuda/", views.help_index, name="help_index"),
    path("ayuda/<slug:slug>/", views.help_page, name="help"),
]
