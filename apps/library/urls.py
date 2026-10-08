from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("documentos/", views.index, name="index"),
    path("documentos/nuevo/", views.new, name="new"),
    path("documentos/<int:pk>/", views.detail, name="detail"),
    path("documentos/<int:pk>/editar/", views.edit, name="edit"),
    path("documentos/<int:pk>/subir/", views.upload, name="upload"),
    path("documentos/<int:pk>/eliminar/", views.delete, name="delete"),
    path("documentos/<int:pk>/archivo/", views.download, name="download"),
    path("documentos/<int:pk>/archivo/<int:version_pk>/", views.download, name="download_version"),
    path("documentos/<int:pk>/vigente/<int:version_pk>/", views.make_current, name="make_current"),
]
