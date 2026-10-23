"""Template tag & filter PCC: class warna status, format percent, dll."""

from django import template
from django.utils.safestring import mark_safe

from apps.richtext import render_html, strip_html

register = template.Library()


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    """Build a querystring from the current request, replacing given keys."""
    request = context.get("request")
    if request is None:
        return "?"
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.filter
def rich(value):
    """HTML ter-sanitasi (aman) untuk catatan & deskripsi kaya."""
    return mark_safe(render_html(value))


@register.filter
def plain(value):
    """Teks polos tanpa tag, untuk preview/kartu ringkas."""
    return strip_html(value)

STATUS_STYLES = {
    **dict.fromkeys(
        ["on_track", "ahead", "done", "completed", "resolved", "mitigated"],
        "pcc-status pcc-status-success",
    ),
    **dict.fromkeys(["at_risk", "high", "medium", "on_hold"], "pcc-status pcc-status-warning"),
    **dict.fromkeys(["delayed", "blocked", "critical", "open"], "pcc-status pcc-status-danger"),
    **dict.fromkeys(
        ["in_progress", "planning", "upcoming", "review"], "pcc-status pcc-status-info"
    ),
}

LEVEL_DOT = {
    "ahead": "bg-foreground",
    "on_track": "bg-foreground",
    "at_risk": "bg-foreground",
    "delayed": "bg-foreground",
    "unknown": "bg-border",
}


@register.filter
def status_style(status):
    return STATUS_STYLES.get(status, "pcc-status pcc-status-neutral")


@register.filter
def level_dot(level):
    return LEVEL_DOT.get(level, "bg-border")


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
        return "text-foreground"
    if v < 0:
        return "text-foreground"
    return "text-muted-foreground"


@register.filter
def level_label(level):
    """Label manusiawi untuk variance level."""
    return {
        "ahead": "Lebih cepat",
        "on_track": "Sesuai rencana",
        "at_risk": "Perlu perhatian",
        "delayed": "Tertinggal",
        "unknown": "Belum ada rencana",
    }.get(level, "Belum ada rencana")


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


@register.filter
def person_name(user):
    """Render optional users without resolving attributes on None in templates."""
    if user is None:
        return ""
    profile = getattr(user, "pcc_profile", None)
    return profile.name if profile else user.get_full_name() or user.username


@register.filter
def status_label(status):
    """Plain-language UI labels; stored statuses and permissions stay unchanged."""
    return {
        "on_track": "Sesuai rencana",
        "ahead": "Lebih cepat",
        "at_risk": "Perlu perhatian",
        "delayed": "Terlambat",
        "planning": "Dalam perencanaan",
        "on_hold": "Ditunda",
        "completed": "Selesai",
        "cancelled": "Dibatalkan",
        "backlog": "Belum dijadwalkan",
        "todo": "Siap dikerjakan",
        "in_progress": "Sedang dikerjakan",
        "blocked": "Terhambat",
        "review": "Menunggu pemeriksaan",
        "done": "Selesai",
        "open": "Terbuka",
        "resolved": "Diselesaikan",
        "closed": "Ditutup",
        "upcoming": "Akan datang",
        "not_started": "Belum dimulai",
    }.get(str(status), status)


@register.filter
def variance_summary(value):
    if value is None:
        return "Rencana progress belum ditetapkan."
    number = float(value)
    if number == 0:
        return "Progress sesuai rencana."
    gap = f"{abs(number):.2f}".replace(".", ",")
    direction = "di bawah" if number < 0 else "di atas"
    return f"{gap} poin persentase {direction} rencana."


@register.filter
def severity_label(value):
    return {"critical": "Kritis", "high": "Tinggi", "medium": "Sedang", "low": "Rendah"}.get(
        value, value
    )
