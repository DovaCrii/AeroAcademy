from django.shortcuts import redirect, render


def waiting(request):
    """Pantalla para quien aún no fue aprobada. Si ya lo está, va a la portada."""
    if request.user.is_approved:
        return redirect("core:home")
    return render(request, "accounts/waiting.html")
