from django.urls import path

from . import change_views, views

app_name = "governance"

urlpatterns = [
    path("approvals/", views.approval_inbox, name="approval_inbox"),
    path("reviews/", views.my_reviews, name="my_reviews"),
    path("approvals/<int:pk>/", views.approval_detail, name="approval_detail"),
    path("approvals/<int:pk>/approve/", views.approval_quick, name="approval_quick"),
    path("approvals/<int:pk>/cancel/", views.approval_cancel, name="approval_cancel"),
    path("projects/<int:pk>/approvals/", views.project_approvals, name="project_approvals"),
    path(
        "projects/<int:pk>/approvals/settings/<str:approval_type>/",
        views.policy_edit,
        name="policy_edit",
    ),
    path("projects/<int:pk>/approvals/plan/", views.request_plan, name="request_plan"),
    path("projects/<int:pk>/approvals/closure/", views.request_closure, name="request_closure"),
    path("tasks/<int:pk>/submit-review/", views.task_submit, name="task_submit"),
    # Change request (R6.2–R6.3)
    path("projects/<int:pk>/changes/new/", change_views.change_create, name="change_create"),
    path("projects/<int:pk>/changes/control/", change_views.change_control, name="change_control"),
    path("changes/<int:pk>/", change_views.change_detail, name="change_detail"),
    path("changes/<int:pk>/edit/", change_views.change_edit, name="change_edit"),
    path("changes/<int:pk>/submit/", change_views.change_submit, name="change_submit"),
    path("changes/<int:pk>/review/", change_views.change_review, name="change_review"),
    path("changes/<int:pk>/apply/", change_views.change_apply, name="change_apply"),
    # Deliverable (R6.4)
    path(
        "projects/<int:pk>/deliverables/",
        change_views.project_deliverables,
        name="project_deliverables",
    ),
    path(
        "projects/<int:pk>/deliverables/new/",
        change_views.deliverable_create,
        name="deliverable_create",
    ),
    path("deliverables/<int:pk>/", change_views.deliverable_detail, name="deliverable_detail"),
    path("deliverables/<int:pk>/edit/", change_views.deliverable_edit, name="deliverable_edit"),
    path(
        "deliverables/<int:pk>/submit/",
        change_views.deliverable_submit,
        name="deliverable_submit",
    ),
    path(
        "deliverables/<int:pk>/review/",
        change_views.deliverable_review,
        name="deliverable_review",
    ),
]
