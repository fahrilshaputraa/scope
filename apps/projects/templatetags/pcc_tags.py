"""Template tag & filter PCC: class warna status, format percent, dll."""

from django import template

register = template.Library()

STATUS_STYLES = {
    # Project
    "planning": "border-blue-200 bg-blue-50 text-blue-700",
    "on_track": "border-emerald-200 bg-emerald-50 text-emerald-700",
    "at_risk": "border-amber-200 bg-amber-50 text-amber-700",
    "delayed": "border-red-200 bg-red-50 text-red-700",
    "completed": "border-slate-200 bg-slate-100 text-slate-700",
    "on_hold": "border-slate-200 bg-slate-100 text-slate-600",
    "cancelled": "border-slate-200 bg-slate-100 text-slate-400",
    # Task status (kanban)
    "backlog": "border-slate-200 bg-slate-100 text-slate-500",
    "todo": "border-slate-200 bg-slate-100 text-slate-700",
    "in_progress": "border-blue-200 bg-blue-50 text-blue-700",
    "blocked": "border-red-200 bg-red-50 text-red-700",
    "review": "border-violet-200 bg-violet-50 text-violet-700",
    "done": "border-emerald-200 bg-emerald-50 text-emerald-700",
    # Issue status
    "open": "border-red-200 bg-red-50 text-red-700",
    "resolved": "border-emerald-200 bg-emerald-50 text-emerald-700",
    "closed": "border-slate-200 bg-slate-100 text-slate-500",
    # Milestone status
    "upcoming": "border-blue-200 bg-blue-50 text-blue-700",
    # Variance level
    "ahead": "border-emerald-200 bg-emerald-50 text-emerald-700",
    "unknown": "border-slate-200 bg-slate-100 text-slate-500",
    # Priority / severity
    "critical": "border-red-200 bg-red-50 text-red-700",
    "high": "border-orange-200 bg-orange-50 text-orange-700",
    "medium": "border-amber-200 bg-amber-50 text-amber-700",
    "low": "border-slate-200 bg-slate-100 text-slate-600",
    "not_started": "border-slate-200 bg-slate-100 text-slate-500",
}

LEVEL_DOT = {
    "ahead": "bg-emerald-500",
    "on_track": "bg-emerald-500",
    "at_risk": "bg-amber-500",
    "delayed": "bg-red-500",
    "unknown": "bg-slate-300",
}


@register.filter
def status_style(status):
    return STATUS_STYLES.get(status, "border-slate-200 bg-slate-100 text-slate-600")


@register.filter
def level_dot(level):
    return LEVEL_DOT.get(level, "bg-slate-300")


@register.filter
def pct(value):
    """Format Decimal/float menjadi '61.60%'; None menjadi '—'."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def fmt2(value, suffix=""):
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}{suffix}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def comp(value):
    """Class warna untuk variance/perbandingan numerik."""
    if value is None:
        return "text-muted-foreground"
    v = float(value)
    if v > 0:
        return "text-emerald-600"
    if v < 0:
        return "text-red-600"
    return "text-muted-foreground"


@register.filter
def level_label(level):
    """Label manusiawi untuk variance level."""
    return {
        "ahead": "Ahead",
        "on_track": "On Track",
        "at_risk": "At Risk",
        "delayed": "Delayed",
        "unknown": "Unknown",
    }.get(level, "No Baseline")


@register.filter
def get_item(value, key):
    """Ambil item dari dict, atau cari key di list of tuples."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(key)
    for k, v in value:
        if str(k) == str(key):
            return v
    return key


@register.filter
def group_count(rows, key):
    """Hitung jumlah project rows berdasarkan status project."""
    from apps.projects.models import ProjectStatus

    def active(r):
        return r["project"].status

    if key == "risk":
        return sum(1 for r in rows if active(r) in (ProjectStatus.AT_RISK, ProjectStatus.DELAYED))
    return sum(1 for r in rows if active(r) == key)


@register.filter
def bar_position(project):
    """Posisi tengah 'hari ini' dalam rentang project → dict % untuk CSS bar."""
    from django.utils import timezone

    span = (project.target_end_date - project.start_date).days or 1
    pos = (timezone.localdate() - project.start_date).days
    pct = max(0, min(100, round(pos / span * 100)))
    return {"left": 0, "width": pct}


@register.filter
def initials(user):
    if not user:
        return "?"
    name = (user.first_name + " " + user.last_name).strip() or user.username
    parts = name.split()
    letters = "".join(p[0] for p in parts[:2])
    return letters.upper()