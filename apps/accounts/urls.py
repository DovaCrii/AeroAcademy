from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("espera/", views.waiting, name="waiting"),
    path("bienvenida/", views.welcome, name="welcome"),
    path("entrar/", views.login, name="login"),
    path("salir/", views.logout, name="logout"),
    path("verificar/", views.verify, name="verify"),
    path("seguridad/2fa/", views.two_factor_setup, name="two_factor"),
    path("registro/<str:token>/", views.signup, name="signup"),
    path("inscripcion/<str:token>/", views.team_signup, name="team_signup"),
]
