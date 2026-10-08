from django.urls import path

from . import views

app_name = "knowledge"

urlpatterns = [
    path("conocimiento/", views.index, name="index"),
    path("conocimiento/nuevo/", views.new, name="new"),
    path("conocimiento/mejoras/", views.improvements, name="improvements"),
    path("conocimiento/mejoras/<int:pk>/", views.improvement, name="improvement"),
    path("conocimiento/<int:pk>/", views.detail, name="detail"),
    path("conocimiento/<int:pk>/editar/", views.edit, name="edit"),
    path("conocimiento/<int:pk>/publicar/", views.publish, name="publish"),
    path("conocimiento/<int:pk>/eliminar/", views.delete, name="delete"),
]
