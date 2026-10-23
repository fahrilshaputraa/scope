from django.urls import path

from . import planning_views, presentation_views, share_views, views
from .exports import export_report

app_name = "projects"

urlpatterns = [
    path("p/<uuid:token>/", share_views.public_project, name="public_project"),
    path("projects/<int:pk>/share/", share_views.project_share, name="project_share"),
    path(
        "projects/<int:pk>/share/reset/",
        share_views.project_share_reset,
        name="project_share_reset",
    ),
    path(
        "projects/<int:pk>/board/feedback/<int:card_id>/",
        presentation_views.feedback_move,
        name="feedback_move",
    ),
    path("projects/<int:pk>/presentation/", presentation_views.presentation, name="presentation"),
    path(
        "projects/<int:pk>/presentation/play/",
        presentation_views.presentation_play,
        name="presentation_play",
    ),
    path(
        "projects/<int:pk>/columns/new/",
        presentation_views.board_column,
        name="board_column_create",
    ),
    path(
        "projects/<int:pk>/columns/<int:column_id>/",
        presentation_views.board_column,
        name="board_column_edit",
    ),
    path(
        "projects/<int:pk>/columns/<int:column_id>/feedback/new/",
        presentation_views.feedback_edit,
        name="feedback_create",
    ),
    path(
        "projects/<int:pk>/columns/<int:column_id>/feedback/<int:card_id>/",
        presentation_views.feedback_edit,
        name="feedback_edit",
    ),
    path(
        "projects/<int:pk>/board/tasks/<int:task_id>/",
        presentation_views.board_move,
        name="board_move",
    ),
    path("projects/import/", planning_views.plan_import, name="plan_import_new"),
    path("projects/import/template/", planning_views.plan_template, name="plan_template_new"),
    path("projects/<int:pk>/import/", planning_views.plan_import, name="plan_import"),
    path("projects/<int:pk>/import/template/", planning_views.plan_template, name="plan_template"),
    path("projects/<int:pk>/export/json/", planning_views.plan_export, name="plan_export"),
    path("projects/<int:pk>/phases/<int:phase_id>/", views.phase_edit, name="phase_edit"),
    path("reports/export/", export_report, name="export_report"),
    path("projects/<int:pk>/members/", views.project_members, name="project_members"),
    path("projects/<int:pk>/risks/new/", views.risk_edit, name="risk_create"),
    path("projects/<int:pk>/risks/<int:rid>/", views.risk_edit, name="risk_edit"),
    path(
        "projects/<int:pk>/timeline/baseline/",
        views.capture_timeline_baseline,
        name="capture_baseline",
    ),
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Projects
    path("projects/", views.project_list, name="project_list"),
    path("search/", views.search, name="search"),
    path("projects/create/", views.project_create, name="project_create"),
    path("projects/<int:pk>/archive/", views.project_archive, name="project_archive"),
    path("projects/<int:pk>/restore/", views.project_restore, name="project_restore"),
    path(
        "projects/<int:pk>/phases/<int:phase_id>/archive/",
        views.phase_archive,
        name="phase_archive",
    ),
    path(
        "projects/<int:pk>/phases/<int:phase_id>/restore/",
        views.phase_restore,
        name="phase_restore",
    ),
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
    path("projects/<int:pk>/history/", views.project_history, name="project_history"),
    path(
        "projects/<int:pk>/history/<int:revision_id>/restore/",
        views.project_history_restore,
        name="project_history_restore",
    ),
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
    path("search/suggest/", views.nav_search, name="nav_search"),
    # Global pages
    path("notes/", views.note_list, name="note_list"),
    path("timeline/", views.timeline_global, name="timeline_global"),
    path("reports/", views.reports, name="reports"),
]
