from django.urls import path

from . import views

app_name = "credentials"

urlpatterns = [
    path("certificados/", views.mine, name="mine"),
    path("certificados/nueva/", views.create, name="create"),
    path("certificados/equipo/", views.team, name="team"),
    path("certificados/vencimientos/", views.expirations, name="expirations"),
    path("certificados/exportar/", views.export_view, name="export"),
    path("certificados/revisar/", views.review_queue, name="review_queue"),
    path("certificados/<int:pk>/", views.detail, name="detail"),
    path("certificados/<int:pk>/editar/", views.edit, name="edit"),
    path("certificados/<int:pk>/archivo/", views.download, name="download"),
    path("certificados/<int:pk>/eliminar/", views.delete, name="delete"),
    path("certificados/<int:pk>/revisar/", views.review, name="review"),
    path("certificados/<int:pk>/promover/", views.promote, name="promote"),
    path("rutas/<slug:slug>/registrar/", views.register_course, name="register_course"),
]
