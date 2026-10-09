from django.urls import path

from . import views

app_name = "dgac"

urlpatterns = [
    path("dgac/", views.home, name="home"),
    path("dgac/prueba/", views.test_home, name="test"),
    path("dgac/prueba/rendir/", views.take, name="take"),
    path("dgac/prueba/<int:pk>/", views.result, name="result"),
    path("dgac/diploma/<int:pk>/", views.diploma, name="diploma"),
    path("dgac/archivo/<str:name>", views.asset, name="asset"),
]
