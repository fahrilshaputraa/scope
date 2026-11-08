"""Audit trail terpadu untuk Admin (R8.4, PRD §20).

Menggabungkan ``ActivityEvent`` (aksi operasional, alasan) dan ``Revision`` (nilai
lama/baru per field) dalam satu urutan waktu, dengan filter per entitas sehingga
satu task, issue, deliverable, atau change request dapat ditelusuri dari awal.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.dateparse import parse_date

from apps.identity.permission_catalog import ROLE_LABELS
from apps.identity.roles import has_perm

from .models import ActivityEvent, Project, Revision, RevisionEntity
from .revisions import decorate_revisions

LIMIT = 200

ENTITY_CHOICES = [
    *RevisionEntity.choices,
    ("approval", "Approval"),
    ("baseline", "Baseline"),
    ("decision", "Decision"),
    ("work_package", "Work package"),
]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@login_required
def audit_trail(request):
    if not has_perm(request.user, "audit.view"):
        raise PermissionDenied
    params = request.GET
    project_id = _int(params.get("project"))
    entity = params.get("entity", "")
    object_id = _int(params.get("id"))
    actor_id = _int(params.get("actor"))
    role = params.get("role", "")
    date_from, date_to = parse_date(params.get("from", "")), parse_date(params.get("to", ""))

    events = ActivityEvent.objects.select_related("project", "actor__pcc_profile")
    revisions = Revision.objects.select_related("project", "actor__pcc_profile")
    if project_id:
        events, revisions = (
            events.filter(project_id=project_id),
            revisions.filter(project_id=project_id),
        )
    if entity:
        events, revisions = events.filter(entity_type=entity), revisions.filter(entity=entity)
    if object_id:
        events = events.filter(entity_id=object_id)
        revisions = revisions.filter(object_id=object_id)
    if actor_id:
        events, revisions = events.filter(actor_id=actor_id), revisions.filter(actor_id=actor_id)
    if role:
        events, revisions = events.filter(active_role=role), revisions.filter(active_role=role)
    if date_from:
        events = events.filter(created_at__date__gte=date_from)
        revisions = revisions.filter(created_at__date__gte=date_from)
    if date_to:
        events = events.filter(created_at__date__lte=date_to)
        revisions = revisions.filter(created_at__date__lte=date_to)

    rows = [
        {
            "kind": "activity",
            "at": e.created_at,
            "actor": e.actor,
            "role": e.active_role,
            "project": e.project,
            "entity": e.entity_type,
            "entity_id": e.entity_id,
            "label": e.object_repr or e.get_action_display(),
            "action": e.get_action_display(),
            "message": e.message,
            "reason": e.reason,
            "changes": [],
        }
        for e in events.order_by("-created_at", "-pk")[:LIMIT]
    ]
    for r in decorate_revisions(revisions.order_by("-created_at", "-pk")[:LIMIT]):
        rows.append(
            {
                "kind": "revision",
                "at": r.created_at,
                "actor": r.actor,
                "role": r.active_role,
                "project": r.project,
                "entity": r.entity,
                "entity_id": r.object_id,
                "label": r.object_repr,
                "action": r.action_label,
                "message": r.summary,
                "reason": (r.changes or {}).get("cancellation_reason", {}).get("new") or "",
                "changes": r.change_rows,
            }
        )
    rows.sort(key=lambda row: row["at"], reverse=True)
    return render(
        request,
        "projects/audit.html",
        {
            "rows": rows[:LIMIT],
            "truncated": len(rows) > LIMIT,
            "projects": Project.all_objects.order_by("code"),
            "actors": User.objects.filter(is_active=True).order_by("username"),
            "entities": ENTITY_CHOICES,
            "roles": list(ROLE_LABELS.items()),
            "filters": {
                "project": project_id or "",
                "entity": entity,
                "id": object_id or "",
                "actor": actor_id or "",
                "role": role,
                "from": params.get("from", ""),
                "to": params.get("to", ""),
            },
            "role_labels": ROLE_LABELS,
        },
    )
