from django.urls import path

from . import forum_views, views

app_name = "community"

urlpatterns = [
    path("foro/", forum_views.index, name="forum"),
    path("foro/nuevo/", forum_views.new, name="thread_new"),
    path("foro/<int:pk>/", forum_views.thread_detail, name="thread"),
    path("foro/<int:pk>/aceptar/<int:post_pk>/", forum_views.accept, name="accept"),
    path("foro/<int:pk>/quitar-aceptada/", forum_views.unaccept, name="unaccept"),
    path("foro/<int:pk>/cerrar/", forum_views.toggle_closed, name="toggle_closed"),
    path("foro/mensaje/<int:pk>/eliminar/", forum_views.delete_post, name="delete_post"),
    path("rutas/<slug:slug>/notas/", views.path_notes, name="path_notes"),
    path("notas/<int:pk>/responder/", views.reply, name="reply"),
    path("notas/<int:pk>/eliminar/", views.delete, name="delete"),
]
