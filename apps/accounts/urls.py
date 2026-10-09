from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("espera/", views.waiting, name="waiting"),
    path("bienvenida/", views.welcome, name="welcome"),
    path("entrar/", views.login, name="login"),
    path("salir/", views.logout, name="logout"),
    path("registro/<str:token>/", views.signup, name="signup"),
]
