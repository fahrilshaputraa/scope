from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.identity.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.work.urls")),
    path("notifications/", include("apps.notifications.urls")),
]
