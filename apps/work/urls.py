from django.urls import path

from . import views

app_name = "work"

urlpatterns = [
    path("tasks/<int:pk>/progress/", views.task_progress, name="task_progress"),
    path("tasks/<int:pk>/attachments/", views.attachment_upload, name="attachment_upload"),
    path("attachments/<int:pk>/download/", views.attachment_download, name="attachment_download"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
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
