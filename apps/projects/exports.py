"""Permission-scoped project exports, shared across CSV, Excel, and PDF."""

import csv
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.identity.permissions import visible_projects

from .project_templates import custom_fields_text
from .services import actual_progress, planned_progress_on, variance


def export_rows(projects, dataset):
    if dataset == "summary":
        headers = [
            "Code",
            "Project",
            "Jenis",
            "PM",
            "Siklus hidup",
            "Health",
            "Phase",
            "Start",
            "Target",
            "Planned %",
            "Actual %",
            "Variance pp",
            "Open issues",
            "Open risks",
            "Next milestone",
            "Current work",
            "Next work",
            "Field tambahan",
        ]
        rows = []
        for p in projects:
            phase, milestone = p.effective_current_phase, p.next_milestone
            rows.append(
                [
                    p.code,
                    p.name,
                    p.get_project_type_display(),
                    str(p.manager or ""),
                    p.get_lifecycle_status_display(),
                    p.get_health_status_display(),
                    str(phase or ""),
                    p.start_date,
                    p.target_end_date,
                    planned_progress_on(p),
                    actual_progress(p),
                    variance(p),
                    p.issues.filter(status__in=["open", "in_progress", "blocked"]).count(),
                    p.risks.filter(status="open").count(),
                    str(milestone or ""),
                    "; ".join(p.tasks.filter(status="in_progress").values_list("title", flat=True)),
                    "; ".join(
                        p.tasks.filter(status__in=["todo", "backlog"]).values_list(
                            "title", flat=True
                        )
                    ),
                    custom_fields_text(p),
                ]
            )
        return headers, rows
    if dataset == "progress":
        return ["Code", "Date", "Planned %", "Actual %", "Variance pp"], [
            [p.code, s.date, s.planned_progress, s.actual_progress, s.variance]
            for p in projects
            for s in p.snapshots.all()
        ]
    if dataset in ("tasks", "timeline"):
        return [
            "Code",
            "Task",
            "Phase",
            "Assignee",
            "Status",
            "Priority",
            "Start",
            "Due",
            "Progress %",
            "Weight",
            "Baseline start",
            "Baseline end",
            "Deviation days",
            "Dependencies",
            "Blocked reason",
        ], [
            [
                p.code,
                t.title,
                str(t.phase or ""),
                t.assignee_names,
                t.get_status_display(),
                t.get_priority_display(),
                t.start_date,
                t.due_date,
                t.display_progress,
                t.weight,
                t.baseline_start_date,
                t.baseline_end_date,
                t.schedule_deviation,
                "; ".join(t.dependencies.values_list("title", flat=True)),
                t.blocked_reason,
            ]
            for p in projects
            for t in p.tasks.select_related("phase", "assignee").prefetch_related(
                "dependencies", "collaborators"
            )
        ]
    if dataset == "issues":
        return ["Code", "Issue", "Severity", "Priority", "Status", "Owner", "Due", "Resolution"], [
            [
                p.code,
                i.title,
                i.get_severity_display(),
                i.get_priority_display(),
                i.get_status_display(),
                str(i.owner or ""),
                i.due_date,
                i.resolution,
            ]
            for p in projects
            for i in p.issues.select_related("owner")
        ]
    if dataset == "milestones":
        return ["Code", "Milestone", "Date", "Status", "Owner", "Description"], [
            [p.code, m.name, m.date, m.get_status_display(), str(m.owner or ""), m.description]
            for p in projects
            for m in p.milestones.select_related("owner")
        ]
    builder = REPORT_BUILDERS.get(dataset)
    if builder is not None:
        return builder(list(projects))
    raise Http404("Jenis report tidak tersedia.")


# ----------------------------------------------------------- report R8.3 ---


def _schedule_deviation(project):
    tasks = [t for t in project.tasks.all() if t.parent_task_id is None]
    due = [t.due_date for t in tasks if t.due_date]
    base = [t.baseline_end_date for t in tasks if t.baseline_end_date]
    if not due or not base:
        return None
    return (max(due) - max(base)).days


def _executive(projects):
    from .services import project_health

    headers = [
        "Code",
        "Project",
        "Owner",
        "PM",
        "Siklus hidup",
        "Health",
        "Rencana %",
        "Aktual %",
        "Selisih pp",
        "Phase",
        "Milestone berikutnya",
        "Issue terbuka",
        "Risiko terbuka",
        "Deviasi jadwal (hari)",
    ]
    rows = []
    for p in projects:
        health = project_health(p)
        rows.append(
            [
                p.code,
                p.name,
                str(p.owner or ""),
                str(p.manager or ""),
                p.get_lifecycle_status_display(),
                p.get_health_status_display(),
                health["planned"],
                health["progress"],
                health["variance"],
                str(p.effective_current_phase or ""),
                str(p.next_milestone or ""),
                health["open_issues"],
                health["risk_count"],
                _schedule_deviation(p),
            ]
        )
    return headers, rows


def _progress_report(projects):
    from datetime import timedelta

    from apps.work.progress import weighted_progress

    headers = [
        "Code",
        "Bagian",
        "Rencana %",
        "Aktual %",
        "Selisih pp",
        "Task selesai",
        "Total task",
        "Tren 14 hari (pp)",
    ]
    rows = []
    since = timezone.localdate() - timedelta(days=14)
    for p in projects:
        roots = [t for t in p.tasks.all() if t.parent_task_id is None]
        snaps = [s for s in p.snapshots.all() if s.actual_progress is not None]
        earlier = [s for s in snaps if s.date <= since]
        trend = None
        if snaps and earlier:
            trend = snaps[-1].actual_progress - earlier[-1].actual_progress
        rows.append(
            [
                p.code,
                "Project",
                planned_progress_on(p),
                actual_progress(p),
                variance(p),
                sum(1 for t in roots if t.is_done),
                len(roots),
                trend,
            ]
        )
        for phase in p.phases.all():
            members = [t for t in roots if t.phase_id == phase.pk]
            rows.append(
                [
                    p.code,
                    f"Phase: {phase.name}",
                    None,
                    weighted_progress(members) if members else None,
                    None,
                    sum(1 for t in members if t.is_done),
                    len(members),
                    None,
                ]
            )
    return headers, rows


def _schedule(projects):
    today = timezone.localdate()
    headers = [
        "Code",
        "Jenis",
        "Nama",
        "Baseline mulai",
        "Baseline selesai",
        "Jadwal mulai",
        "Jadwal selesai",
        "Deviasi (hari)",
        "Keterangan",
    ]
    rows = []
    for p in projects:
        for t in p.tasks.all():
            note = "Terlambat" if t.is_overdue else ("Selesai" if t.is_done else "")
            rows.append(
                [
                    p.code,
                    "Task",
                    t.title,
                    t.baseline_start_date,
                    t.baseline_end_date,
                    t.start_date,
                    t.due_date,
                    t.schedule_deviation,
                    note,
                ]
            )
        for m in p.milestones.all():
            if m.status == "completed":
                note = "Tercapai"
            elif m.date < today or m.status == "delayed":
                note = "Terlambat"
            else:
                note = "Akan datang"
            rows.append([p.code, "Milestone", m.name, None, None, None, m.date, None, note])
    return headers, rows


def _task_report(projects):
    from collections import OrderedDict

    headers = [
        "Code",
        "Pelaksana",
        "Total",
        "Selesai",
        "Sedang dikerjakan",
        "Terhambat",
        "Menunggu pemeriksaan",
        "Terlambat",
    ]
    rows = []
    for p in projects:
        groups = OrderedDict()
        tasks = list(p.tasks.all())
        for t in tasks:
            name = str(t.assignee) if t.assignee_id else "Belum ditugaskan"
            groups.setdefault(name, []).append(t)
        for name, items in [("Semua pelaksana", tasks), *groups.items()]:
            rows.append(
                [
                    p.code,
                    name,
                    len(items),
                    sum(1 for t in items if t.status == "done"),
                    sum(1 for t in items if t.status == "in_progress"),
                    sum(1 for t in items if t.status == "blocked"),
                    sum(1 for t in items if t.status == "review"),
                    sum(1 for t in items if t.is_overdue),
                ]
            )
    return headers, rows


def _management(projects):
    from .dashboards import portfolio_health
    from .services import project_health

    attention = {
        row["project"].pk: row["reasons"] for row in portfolio_health(projects)["attention"]
    }
    headers = [
        "Code",
        "Project",
        "Owner",
        "Health",
        "Rencana %",
        "Aktual %",
        "Selisih pp",
        "Issue kritis",
        "Risiko teratas",
        "Milestone berikutnya",
        "Perlu perhatian",
    ]
    rows = []
    for p in projects:
        health = project_health(p)
        rows.append(
            [
                p.code,
                p.name,
                str(p.owner or ""),
                p.get_health_status_display(),
                health["planned"],
                health["progress"],
                health["variance"],
                health["critical_issues"],
                health["risk_top_severity"] or "",
                str(p.next_milestone or ""),
                "; ".join(attention.get(p.pk, [])),
            ]
        )
    return headers, rows


def _risks(projects):
    headers = [
        "Code",
        "Risiko",
        "Kemungkinan",
        "Dampak",
        "Skor",
        "Tingkat",
        "Status",
        "Owner",
        "Mitigasi",
        "Tanggal tinjau",
    ]
    return headers, [
        [
            p.code,
            r.title,
            r.probability,
            r.impact,
            r.score,
            r.get_severity_display(),
            r.get_status_display(),
            str(r.owner or ""),
            r.mitigation,
            r.review_date,
        ]
        for p in projects
        for r in p.risks.select_related("owner")
    ]


def _deliverables(projects):
    headers = [
        "Code",
        "Deliverable",
        "Task",
        "Pemilik",
        "Penerima",
        "Target",
        "Diserahkan",
        "Status",
        "Kriteria",
    ]
    return headers, [
        [
            p.code,
            d.name,
            str(d.task or ""),
            str(d.owner or ""),
            str(d.reviewer or p.owner or ""),
            d.due_date,
            d.submission_date,
            d.get_status_display(),
            d.acceptance_criteria,
        ]
        for p in projects
        for d in p.deliverables.select_related("task", "owner", "reviewer")
    ]


REPORT_BUILDERS = {
    "executive": _executive,
    "progress_report": _progress_report,
    "schedule": _schedule,
    "task_report": _task_report,
    "management": _management,
    "risks": _risks,
    "deliverables": _deliverables,
}

#: Laporan bernama di halaman Laporan (R8.3); dataset lain hanya untuk unduhan.
REPORTS = {
    "executive": ("Executive Summary", "Ringkasan eksekutif per project."),
    "progress_report": ("Progress", "Rencana, aktual, tren, dan progress per phase."),
    "schedule": ("Jadwal", "Baseline vs jadwal saat ini, deviasi, dan milestone."),
    "task_report": ("Task", "Distribusi task per status dan pelaksana."),
    "management": ("Manajemen", "Portfolio, health, dan hal yang perlu perhatian."),
}

#: Dataset berisi detail task teknis: tidak untuk role Management (PRD §21.4).
TASK_DETAIL_DATASETS = {"tasks", "timeline", "schedule"}
#: Dataset internal: tidak untuk role tanpa ``project.view_internal`` (Client).
INTERNAL_DATASETS = {"issues", "risks", "summary"}


def dataset_problem(user, dataset) -> str:
    from apps.identity.permissions import can_view_internal, is_management

    if dataset in TASK_DETAIL_DATASETS and is_management(user) and not user.is_staff:
        return "Laporan ini berisi detail task teknis dan tidak tersedia untuk role Management."
    if dataset in INTERNAL_DATASETS and not can_view_internal(user):
        return "Laporan ini berisi data internal project."
    return ""


def report_projects(user):
    from .services import with_project_metrics

    return (
        with_project_metrics(visible_projects(user)).prefetch_related("snapshots").order_by("code")
    )


def safe_cell(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)
    # Never allow untrusted titles to become spreadsheet formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@login_required
def export_report(request):
    """Unduh laporan; butuh ``report.export`` dan hanya memuat data yang boleh dilihat."""
    from django.core.exceptions import PermissionDenied

    from apps.identity.roles import has_perm

    if not has_perm(request.user, "report.export"):
        raise PermissionDenied
    problem = dataset_problem(request.user, request.GET.get("dataset", "summary"))
    if problem:
        raise PermissionDenied(problem)
    projects = report_projects(request.user)
    if request.GET.get("project"):
        try:
            project_id = int(request.GET["project"])
        except ValueError as exc:
            raise Http404("Project tidak valid.") from exc
        project = get_object_or_404(projects, pk=project_id)
        projects = projects.filter(pk=project.pk)
    dataset = request.GET.get("dataset", "summary")
    headers, rows = export_rows(projects, dataset)
    kind = request.GET.get("format", "csv")
    filename = f"pcc-{dataset}-{timezone.localdate().isoformat()}"
    if kind == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows([[safe_cell(v) for v in row] for row in rows])
        response = HttpResponse(
            "\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8"
        )
    elif kind == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = dataset.title()
        sheet.append(headers)
        for row in rows:
            sheet.append([safe_cell(v) if isinstance(v, str) else v for v in row])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0075DE")
        for i, header in enumerate(headers, 1):
            sheet.column_dimensions[get_column_letter(i)].width = max(16, min(36, len(header) + 8))
        output = BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif kind == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A3, A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import (
            Image,
            LongTable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )

        output = BytesIO()
        size = landscape(A3 if len(headers) > 10 else A4)
        doc = SimpleDocTemplate(
            output, pagesize=size, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
        )
        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle("Cell", fontSize=7, leading=9, wordWrap="CJK")
        table_data = [
            [Paragraph(escape(safe_cell(v)), cell_style) for v in row] for row in [headers, *rows]
        ]
        table = LongTable(
            table_data, colWidths=[(size[0] - 48) / len(headers)] * len(headers), repeatRows=1
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f3fe")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#0075de")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f6f5f4")],
                    ),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        doc.build(
            [
                Image(
                    str(settings.BASE_DIR / "static/brand/scope-horizontal.png"),
                    width=140,
                    height=140 * 256 / 710,
                    hAlign="LEFT",
                ),
                Spacer(1, 10),
                Paragraph(f"Scope — {dataset.title()}", styles["Title"]),
                Paragraph(str(timezone.localdate()), styles["Normal"]),
                Spacer(1, 16),
                table,
            ]
        )
        response = HttpResponse(output.getvalue(), content_type="application/pdf")
    else:
        raise Http404("Format export tidak tersedia.")
    response["Content-Disposition"] = f'attachment; filename="{filename}.{kind}"'
    return response


@login_required
def report_detail(request, kind):
    """Halaman laporan R8.3; isinya sama persis dengan unduhan dataset yang sama."""
    from django.core.exceptions import PermissionDenied
    from django.shortcuts import render

    from apps.identity.roles import has_perm

    if kind not in REPORTS:
        raise Http404("Jenis laporan tidak tersedia.")
    if not has_perm(request.user, "report.view"):
        raise PermissionDenied
    problem = dataset_problem(request.user, kind)
    if problem:
        raise PermissionDenied(problem)
    projects = report_projects(request.user)
    selected = None
    if request.GET.get("project", "").isdigit():
        selected = get_object_or_404(projects, pk=int(request.GET["project"]))
        rows_source = projects.filter(pk=selected.pk)
    else:
        rows_source = projects
    headers, rows = export_rows(rows_source, kind)
    title, description = REPORTS[kind]
    return render(
        request,
        "projects/portfolio/report_detail.html",
        {
            "kind": kind,
            "title": title,
            "description": description,
            "headers": headers,
            "rows": rows,
            "projects": projects,
            "selected": selected,
            "reports": [
                (key, label)
                for key, (label, _) in REPORTS.items()
                if not dataset_problem(request.user, key)
            ],
            "can_export": has_perm(request.user, "report.export"),
        },
    )
