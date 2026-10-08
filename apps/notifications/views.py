from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import Notification


@require_GET
def inbox(request):
    return render(request, "notifications/inbox.html", {"items": services.recent(request.user)})


@require_POST
def read(request, pk=None):
    """Marca un aviso (o todos) como leído; con un aviso, sigue su enlace si es local."""
    if pk is None:
        services.mark_read(request.user)
        return redirect("notifications:inbox")
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    services.mark_read(request.user, pk)
    target = notification.url
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect("notifications:inbox")
