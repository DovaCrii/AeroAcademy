from django.urls import path

from . import views

app_name = "diplomas"

urlpatterns = [
    path("diplomas/<slug:slug>/", views.detail, name="detail"),
]
