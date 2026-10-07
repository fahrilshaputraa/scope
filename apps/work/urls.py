from django.urls import path

from . import views

app_name = "work"

urlpatterns = [
    path("my-tasks/", views.my_tasks, name="my_tasks"),
    # Tasks
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_update, name="task_update"),
    path("tasks/<int:pk>/status/", views.task_status, name="task_status"),
    path("tasks/<int:pk>/dates/", views.task_dates, name="task_dates"),
    # Issues
    path("issues/", views.issue_list, name="issue_list"),
    path("issues/new/", views.issue_create, name="issue_create"),
    path("issues/<int:pk>/", views.issue_update, name="issue_update"),
]