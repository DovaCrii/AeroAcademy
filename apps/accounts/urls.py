from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("espera/", views.waiting, name="waiting"),
    path("bienvenida/", views.welcome, name="welcome"),
    path("entrar/", views.login, name="login"),
    path("salir/", views.logout, name="logout"),
    path("entrar/tailscale/", views.tailscale_login, name="tailscale_login"),
    path("cuenta/", views.account, name="account"),
    path("cuenta/contrasena/", views.password_change, name="password_change"),
    path("verificar/", views.verify, name="verify"),
    path("seguridad/2fa/", views.two_factor_setup, name="two_factor"),
    path("registro/<str:token>/", views.signup, name="signup"),
    path("inscripcion/<str:token>/", views.team_signup, name="team_signup"),
]
