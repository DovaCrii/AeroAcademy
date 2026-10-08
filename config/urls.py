from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.paths.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.core.urls")),
]
