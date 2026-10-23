from django.urls import path

from . import views

app_name = "work"

urlpatterns = [
    path("tasks/<int:pk>/progress/", views.task_progress, name="task_progress"),
    path("tasks/<int:pk>/attachments/", views.attachment_upload, name="attachment_upload"),
    path("attachments/<int:pk>/download/", views.attachment_download, name="attachment_download"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
    path("my-tasks/", views.my_tasks, name="my_tasks"),
    path("mentions/suggest/", views.mention_suggest, name="mention_suggest"),
    path("comments/", views.comment_create, name="comment_create"),
    # Tasks
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/archive/", views.task_archive, name="task_archive"),
    path("tasks/<int:pk>/restore/", views.task_restore, name="task_restore"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_update, name="task_update"),
    path("tasks/<int:pk>/status/", views.task_status, name="task_status"),
    path("tasks/<int:pk>/dates/", views.task_dates, name="task_dates"),
    # Issues
    path("issues/", views.issue_list, name="issue_list"),
    path("issues/new/", views.issue_create, name="issue_create"),
    path("issues/<int:pk>/archive/", views.issue_archive, name="issue_archive"),
    path("issues/<int:pk>/restore/", views.issue_restore, name="issue_restore"),
    path("issues/<int:pk>/", views.issue_update, name="issue_update"),
]
