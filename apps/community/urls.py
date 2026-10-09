from django.urls import path

from . import forum_views, moderation_views, views

app_name = "community"

urlpatterns = [
    path("foro/", forum_views.index, name="forum"),
    path("foro/nuevo/", forum_views.new, name="thread_new"),
    path("foro/<int:pk>/", forum_views.thread_detail, name="thread"),
    path("foro/<int:pk>/aceptar/<int:post_pk>/", forum_views.accept, name="accept"),
    path("foro/<int:pk>/quitar-aceptada/", forum_views.unaccept, name="unaccept"),
    path("foro/<int:pk>/cerrar/", forum_views.toggle_closed, name="toggle_closed"),
    path("foro/reaccion/<str:kind>/<int:pk>/", forum_views.react, name="react"),
    path("foro/<int:pk>/encuesta/votar/", forum_views.poll_vote, name="poll_vote"),
    path("foro/<int:pk>/encuesta/", forum_views.poll_add, name="poll_add"),
    path("foro/<int:pk>/moderar/limpiar/", moderation_views.clear_opinions, name="clear_opinions"),
    path("foro/mensaje/<int:pk>/eliminar/", forum_views.delete_post, name="delete_post"),
    path("moderacion/", moderation_views.dashboard, name="moderation"),
    path(
        "moderacion/personas/<int:pk>/aprobar/",
        moderation_views.approve_person,
        name="approve_person",
    ),
    path(
        "moderacion/personas/<int:pk>/rechazar/",
        moderation_views.reject_person,
        name="reject_person",
    ),
    path(
        "moderacion/reportes/<int:pk>/resolver/",
        moderation_views.resolve_report,
        name="resolve_report",
    ),
    path("moderacion/anuncios/nuevo/", moderation_views.new_announcement, name="new_announcement"),
    path(
        "moderacion/anuncios/<int:pk>/retirar/",
        moderation_views.remove_announcement,
        name="remove_announcement",
    ),
    path("foro/<int:pk>/moderar/", moderation_views.moderate_thread, name="moderate_thread"),
    path("foro/mensaje/<int:pk>/moderar/", moderation_views.moderate_post, name="moderate_post"),
    path("notas/<int:pk>/moderar/", moderation_views.moderate_note, name="moderate_note"),
    path("reportar/<str:kind>/<int:pk>/", moderation_views.report, name="report"),
    path("rutas/<slug:slug>/notas/", views.path_notes, name="path_notes"),
    path("notas/<int:pk>/responder/", views.reply, name="reply"),
    path("notas/<int:pk>/eliminar/", views.delete, name="delete"),
]
