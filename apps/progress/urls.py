from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("rutas/<slug:slug>/hitos/<str:key>/", views.toggle_milestone, name="toggle_milestone"),
    path("rutas/<slug:slug>/quiz/<str:key>/", views.answer_quiz, name="answer_quiz"),
    path("rutas/<slug:slug>/meta/", views.set_goal, name="set_goal"),
]
