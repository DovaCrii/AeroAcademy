from django.urls import path

from . import views
from .admin_urls import urlpatterns as admin_urlpatterns

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    *admin_urlpatterns,
]
