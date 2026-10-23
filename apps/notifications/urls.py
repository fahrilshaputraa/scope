from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.center, name="center"),
    path("watch/project/<int:pk>/", views.watch_project, name="watch_project"),
    path("unwatch/project/<int:pk>/", views.unwatch_project, name="unwatch_project"),
    path("watch/task/<int:pk>/", views.watch_task, name="watch_task"),
    path("unwatch/task/<int:pk>/", views.unwatch_task, name="unwatch_task"),
    path("read-all/", views.mark_all_read, name="mark_all_read"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("<int:pk>/unread/", views.mark_unread, name="mark_unread"),
]
