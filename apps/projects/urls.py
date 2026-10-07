from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Projects
    path("projects/", views.project_list, name="project_list"),
    path("projects/create/", views.project_create, name="project_create"),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    # Project tabs
    path("projects/<int:pk>/progress/", views.project_progress, name="project_progress"),
    path("projects/<int:pk>/timeline/", views.project_timeline, name="project_timeline"),
    path("projects/<int:pk>/tasks/", views.project_tasks, name="project_tasks"),
    path("projects/<int:pk>/issues/", views.project_issues, name="project_issues"),
    path("projects/<int:pk>/milestones/", views.project_milestones, name="project_milestones"),
    path("projects/<int:pk>/notes/", views.project_notes, name="project_notes"),
    path("projects/<int:pk>/activity/", views.project_activity, name="project_activity"),
    # CRUD — phases / milestones / baseline / notes / decisions
    path("projects/<int:pk>/phases/create/", views.phase_create, name="phase_create"),
    path(
        "projects/<int:pk>/milestones/create/",
        views.milestone_create,
        name="milestone_create",
    ),
    path(
        "projects/<int:pk>/milestones/<int:mid>/",
        views.milestone_update,
        name="milestone_update",
    ),
    path(
        "projects/<int:pk>/milestones/<int:mid>/delete/",
        views.milestone_delete,
        name="milestone_delete",
    ),
    path("projects/<int:pk>/baseline/add/", views.baseline_add, name="baseline_add"),
    path(
        "projects/<int:pk>/baseline/<int:bpid>/delete/",
        views.baseline_delete,
        name="baseline_delete",
    ),
    path("projects/<int:pk>/snapshot/", views.snapshot_now, name="snapshot_now"),
    path("projects/<int:pk>/notes/create/", views.note_create, name="note_create"),
    path("projects/<int:pk>/notes/<int:nid>/edit/", views.note_edit, name="note_edit"),
    path("projects/<int:pk>/notes/<int:nid>/delete/", views.note_delete, name="note_delete"),
    path("projects/<int:pk>/decisions/create/", views.decision_create, name="decision_create"),
    path(
        "projects/<int:pk>/decisions/<int:did>/delete/",
        views.decision_delete,
        name="decision_delete",
    ),
    # Global pages
    path("notes/", views.note_list, name="note_list"),
    path("timeline/", views.timeline_global, name="timeline_global"),
    path("reports/", views.reports, name="reports"),
]