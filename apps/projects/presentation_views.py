"""Project board content and server-rendered, stable presentation snapshots."""

import json
from copy import copy
from datetime import timedelta
from math import ceil

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.form_widgets import style_form
from apps.identity.permissions import can_edit_task, can_manage_project
from apps.richtext import SanitizeRichTextMixin
from apps.work.models import OPEN_ISSUE_STATUSES, TASK_STATUS_LABELS, Task

from .models import ActivityAction, BoardColumn, FeedbackCard, PresentationConfig
from .services import record_activity, timeline_data
from .views import _project_or_404, progress_chart_data, project_context

DEFAULT_SECTIONS = [
    ("overview", "Rencana vs progress"),
    ("ongoing", "Sedang dikerjakan"),
    ("next", "Periode berikutnya"),
    ("issues", "Daftar masalah"),
    ("thanks", "Terima kasih"),
]


def available_sections(project):
    return dict(
        DEFAULT_SECTIONS + [(f"column:{c.pk}", c.title) for c in project.board_columns.all()]
    )


def resolve_sections(project, saved):
    available = available_sections(project)
    result, seen = [], set()
    for row in saved if isinstance(saved, list) else []:
        if (
            isinstance(row, dict)
            and isinstance(row.get("key"), str)
            and row["key"] in available
            and row["key"] not in seen
        ):
            key = row["key"]
            seen.add(key)
            result.append(
                {
                    "key": key,
                    "title": row.get("title") or available[key],
                    "enabled": bool(row.get("enabled", True)),
                    "show_details": bool(row.get("show_details", True)),
                }
            )
    for key, title in available.items():
        if key not in seen:
            result.append(
                {
                    "key": key,
                    "title": title,
                    "enabled": not key.startswith("column:"),
                    "show_details": True,
                }
            )
    return result


class PresentationForm(forms.Form):
    period_start = forms.DateField(
        label="Mulai periode berikutnya", widget=forms.DateInput(attrs={"type": "date"})
    )
    period_end = forms.DateField(
        label="Akhir periode berikutnya", widget=forms.DateInput(attrs={"type": "date"})
    )
    sections = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        style_form(self)

    def clean_sections(self):
        try:
            rows = json.loads(self.cleaned_data["sections"])
        except (ValueError, TypeError):
            raise forms.ValidationError("Susunan slide tidak valid.") from None
        available = available_sections(self.project)
        if not isinstance(rows, list) or len(rows) != len(available):
            raise forms.ValidationError("Kolom telah berubah. Muat ulang untuk menyusun slide.")
        seen = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("key"), str)
                or row["key"] not in available
                or row["key"] in seen
            ):
                raise forms.ValidationError("Sumber slide tidak valid.")
            if (
                not isinstance(row.get("enabled"), bool)
                or not isinstance(row.get("title"), str)
                or not 1 <= len(row["title"].strip()) <= 100
            ):
                raise forms.ValidationError("Judul slide wajib diisi, maksimal 100 karakter.")
            if not isinstance(row.get("show_details", True), bool):
                raise forms.ValidationError("Pilihan detail slide tidak valid.")
            row["title"] = row["title"].strip()
            seen.add(row["key"])
        if not any(row["enabled"] for row in rows):
            raise forms.ValidationError("Aktifkan minimal satu slide.")
        return rows

    def clean(self):
        data = super().clean()
        start, end = data.get("period_start"), data.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Tanggal akhir harus setelah tanggal mulai.")
        return data


@login_required
@require_http_methods(["GET", "POST"])
def presentation(request, pk):
    project = _project_or_404(request, pk)
    config = PresentationConfig.objects.filter(project=project).first()
    rows = resolve_sections(project, config.sections if config else [])
    today = timezone.localdate()
    initial = {
        "period_start": config.period_start
        if config and config.period_start
        else today + timedelta(days=1),
        "period_end": config.period_end
        if config and config.period_end
        else today + timedelta(days=14),
        "sections": json.dumps(rows),
    }
    if request.method == "POST" and not can_manage_project(request.user, project):
        raise PermissionDenied
    form = PresentationForm(
        request.POST if request.method == "POST" else None, initial=initial, project=project
    )
    if request.method == "POST" and form.is_valid():
        PresentationConfig.objects.update_or_create(project=project, defaults=form.cleaned_data)
        record_activity(
            project, request.user, ActivityAction.PROJECT_UPDATED, "Susunan presentasi diperbarui."
        )
        return redirect(
            "projects:presentation_play"
            if request.POST.get("action") == "play"
            else "projects:presentation",
            pk=pk,
        )
    if form.is_bound:
        try:
            submitted = json.loads(form.data.get("sections", ""))
            rows = resolve_sections(project, submitted)
        except (ValueError, TypeError):
            pass
    return render(
        request,
        "projects/presentation_setup.html",
        {
            **project_context(request, project, "overview"),
            "form": form,
            "sections": rows,
            "saved": bool(config),
        },
    )


def content_chunks(text, size=700):
    """Keep all prose, breaking at whitespace for readable continuation slides."""
    parts = []
    while len(text) > size:
        boundary = text.rfind(" ", 0, size)
        if boundary < size // 2:
            boundary = size
        parts.append(text[:boundary])
        text = text[boundary:]
    return parts + [text]


def paginate_content(items, kind, limit, show_details):
    expanded = []
    for item in items:
        obj = item.get("feedback") or item.get("task") if kind == "column" else item
        fields = (
            ["description", "resolution"]
            if kind == "issues"
            else ["description"]
            if kind == "column"
            else ["blocked_reason"]
        )
        chunks = {field: content_chunks(getattr(obj, field, "")) for field in fields}
        parts = max(len(value) for value in chunks.values()) if show_details else 1
        for part in range(parts):
            clone = copy(obj)
            for field, values in chunks.items():
                setattr(clone, field, values[part] if part < len(values) else "")
            if parts > 1:
                clone.title = f"{obj.title} (lanjutan {part + 1}/{parts})"
            prose = sum(len(getattr(clone, field, "")) for field in fields) if show_details else 0
            cost = max(1, ceil(prose / 300))
            record = (
                {"feedback" if "feedback" in item else "task": clone} if kind == "column" else clone
            )
            expanded.append((record, cost))
    pages, page, used = [], [], 0
    for record, cost in expanded:
        if page and used + cost > limit:
            pages.append(page)
            page, used = [], 0
        page.append(record)
        used += cost
    return pages + [page] if page else pages or [[]]


def presentation_slides(project, sections, start, end):
    tasks = list(
        project.tasks.select_related("phase", "assignee").prefetch_related("collaborators")
    )
    plans = {
        row["task"].pk: row["planned_percent"] for row in timeline_data(project)["timeline_rows"]
    }
    for task in tasks:
        task.presentation_plan = plans.get(task.pk)
        task.presentation_status = TASK_STATUS_LABELS[task.status]
    slides = []
    for section in sections:
        if not section["enabled"]:
            continue
        key = section["key"]
        kind, items, limit = key, [], 6
        if key == "ongoing":
            items = [t for t in tasks if t.status in ("in_progress", "blocked", "review")]
        elif key == "next":
            # Carry unfinished ongoing work, plus planned work overlapping the chosen period.
            items = [
                t
                for t in tasks
                if t.status != "done"
                and (
                    t.status in ("in_progress", "blocked", "review")
                    or (
                        t.start_date
                        and t.start_date <= end
                        and (t.due_date or t.start_date) >= start
                    )
                )
            ]
        elif key == "issues":
            items = list(
                project.issues.filter(status__in=OPEN_ISSUE_STATUSES)
                .select_related("owner", "task")
                .order_by("due_date", "pk")
            )
            items.sort(
                key=lambda i: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(i.severity, 4)
            )
            limit = 3
        elif key.startswith("column:"):
            column = project.board_columns.get(pk=int(key.split(":")[1]))
            kind = "column"
            items = [
                {"feedback": f}
                for f in column.feedback_cards.select_related("owner", "linked_task")
            ] + [{"task": t} for t in tasks if t.board_column_id == column.pk]
            limit = 4
        pages = (
            paginate_content(items, kind, limit, section.get("show_details", True))
            if kind not in ("overview", "thanks")
            else [[]]
        )
        for page, records in enumerate(pages, 1):
            slides.append(
                {
                    **section,
                    "kind": kind,
                    "items": records,
                    "page": page,
                    "pages": len(pages),
                    "count": len(items),
                }
            )
    return slides


@login_required
def presentation_play(request, pk):
    project = _project_or_404(request, pk)
    config = PresentationConfig.objects.filter(project=project).first()
    today = timezone.localdate()
    start = config.period_start if config and config.period_start else today + timedelta(days=1)
    end = config.period_end if config and config.period_end else today + timedelta(days=14)
    sections = resolve_sections(project, config.sections if config else [])
    chart = progress_chart_data(
        list(project.baseline_points.all()),
        list(project.snapshots.order_by("date")),
        project.actual_progress,
    )
    return render(
        request,
        "projects/presentation_play.html",
        {
            "project": project,
            "slides": presentation_slides(project, sections, start, end),
            "chart": chart,
            "chart_has_plan": any(v is not None for v in chart["planned"]),
            "captured_at": timezone.now(),
            "period_start": start,
            "period_end": end,
        },
    )


class ColumnForm(forms.ModelForm):
    class Meta:
        model = BoardColumn
        fields = ["title"]
        labels = {"title": "Nama kolom"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class FeedbackForm(SanitizeRichTextMixin, forms.ModelForm):
    class Meta:
        model = FeedbackCard
        fields = ["title", "description", "status", "owner", "due_date", "linked_task"]
        labels = {"title": "Judul feedback", "linked_task": "Task terkait", "owner": "PIC"}
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["linked_task"].queryset = project.tasks.all()
        self.fields["owner"].queryset = (
            self.fields["owner"]
            .queryset.filter(Q(member_projects=project) | Q(pk=project.manager_id))
            .distinct()
        )
        self.fields["linked_task"].help_text = (
            "Hubungkan dengan task jika feedback sudah menjadi pekerjaan. "
            "Progress dihitung dari task tersebut."
        )
        style_form(
            self, primary=["title", "description", "status", "owner", "due_date", "linked_task"]
        )


@login_required
@require_http_methods(["GET", "POST"])
def board_column(request, pk, column_id=None):
    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    instance = (
        get_object_or_404(BoardColumn, project=project, pk=column_id)
        if column_id
        else BoardColumn(project=project, order=project.board_columns.count())
    )
    form = ColumnForm(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_UPDATED,
            f'Kolom Kanban "{instance.title}" disimpan.',
        )
        return redirect("projects:project_tasks", pk=pk)
    return render(
        request,
        "projects/board_form.html",
        {
            "form": form,
            "title": "Edit kolom" if column_id else "Tambah kolom Kanban",
            "subtitle": (
                "Kolom tambahan untuk feedback dan pengelompokan task. "
                "Bisa ditampilkan sebagai slide."
            ),
            "back_url": reverse("projects:project_tasks", args=[pk]),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def feedback_edit(request, pk, column_id, card_id=None):
    project = _project_or_404(request, pk)
    column = get_object_or_404(BoardColumn, project=project, pk=column_id)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    instance = (
        get_object_or_404(FeedbackCard, column=column, pk=card_id)
        if card_id
        else FeedbackCard(column=column)
    )
    form = FeedbackForm(
        request.POST if request.method == "POST" else None, instance=instance, project=project
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        record_activity(
            project,
            request.user,
            ActivityAction.PROJECT_UPDATED,
            f'Feedback "{instance.title}" disimpan.',
        )
        return redirect("projects:project_tasks", pk=pk)
    return render(
        request,
        "projects/board_form.html",
        {
            "form": form,
            "title": "Edit feedback" if card_id else "Tambah feedback",
            "subtitle": f"{column.title} · Feedback tidak menambah bobot progress project.",
            "back_url": reverse("projects:project_tasks", args=[pk]),
        },
    )


@login_required
@require_http_methods(["POST", "PATCH"])
@transaction.atomic
def board_move(request, pk, task_id):
    from apps.work.views import _params

    project = _project_or_404(request, pk)
    task = get_object_or_404(Task, project=project, pk=task_id)
    if not can_edit_task(request.user, task):
        raise PermissionDenied
    try:
        column_id = int(_params(request).get("column", ""))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Pilih kolom yang valid."}, status=400)
    column = get_object_or_404(BoardColumn, project=project, pk=column_id)
    task.board_column = column
    try:
        task.full_clean(exclude=["dependencies"])
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": " ".join(exc.messages)}, status=400)
    task.save(update_fields=["board_column", "updated_at"])
    record_activity(
        project,
        request.user,
        ActivityAction.TASK_UPDATED,
        f'Task "{task.title}" dipindahkan ke kolom "{column.title}".',
    )
    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST", "PATCH"])
@transaction.atomic
def feedback_move(request, pk, card_id):
    from apps.work.views import _params

    project = _project_or_404(request, pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied
    card = get_object_or_404(FeedbackCard, column__project=project, pk=card_id)
    try:
        column_id = int(_params(request).get("column", ""))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Pilih kolom yang valid."}, status=400)
    column = get_object_or_404(BoardColumn, project=project, pk=column_id)
    card.column = column
    card.save(update_fields=["column", "updated_at"])
    record_activity(
        project,
        request.user,
        ActivityAction.PROJECT_UPDATED,
        f'Feedback "{card.title}" dipindahkan ke kolom "{column.title}".',
    )
    return JsonResponse({"ok": True})
