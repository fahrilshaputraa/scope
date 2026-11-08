from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("", views.index, name="index"),
    path("teams/new/", views.webhook_create, name="webhook_create"),
    path("teams/<int:pk>/edit/", views.webhook_edit, name="webhook_edit"),
    path("teams/<int:pk>/delete/", views.webhook_delete, name="webhook_delete"),
    path("teams/<int:pk>/test/", views.webhook_test, name="webhook_test"),
    path("calendar/reset/", views.feed_reset, name="feed_reset"),
    path("calendar/project/", views.project_calendar_pick, name="project_calendar_pick"),
    path("calendar/<slug:token>.ics", views.user_feed_view, name="user_feed"),
    path("projects/<int:pk>/calendar.ics", views.project_calendar, name="project_calendar"),
    path("outlook/connect/", views.outlook_connect, name="outlook_connect"),
    path("outlook/callback/", views.outlook_callback, name="outlook_callback"),
    path("outlook/disconnect/", views.outlook_disconnect, name="outlook_disconnect"),
    path("outlook/add/<str:kind>/<int:pk>/", views.outlook_add, name="outlook_add"),
]
