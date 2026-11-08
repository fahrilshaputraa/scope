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
def rich_mentions(value):
    """HTML ter-sanitasi dengan sebutan ``@username`` disorot."""
    return mark_safe(render_html(value, mentions=True))


@register.filter
def plain(value):
    """Teks polos tanpa tag, untuk preview/kartu ringkas."""
    return strip_html(value)


STATUS_STYLES = {
    **dict.fromkeys(
        [
            "on_track",
            "ahead",
            "done",
            "completed",
            "resolved",
            "mitigated",
            "approved",
            "accepted",
            "applied",
            "active",
        ],
        "pcc-status pcc-status-success",
    ),
    "rejected": "pcc-status pcc-status-danger",
    **dict.fromkeys(["pending", "submitted", "under_review"], "pcc-status pcc-status-info"),
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
    """Hitung jumlah project rows berdasarkan health project."""
    from apps.projects.models import HealthStatus

    def active(r):
        return r["project"].health_status

    if key == "risk":
        return sum(
            1
            for r in rows
            if active(r) in (HealthStatus.AT_RISK, HealthStatus.DELAYED, HealthStatus.CRITICAL)
        )
    return sum(1 for r in rows if active(r) == key)


_LIFECYCLE_STYLES = {
    "draft": "pcc-status pcc-status-neutral",
    "planning": "pcc-status pcc-status-info",
    "in_progress": "pcc-status pcc-status-info",
    "on_hold": "pcc-status pcc-status-warning",
    "completed": "pcc-status pcc-status-success",
    "cancelled": "pcc-status pcc-status-neutral",
}
_HEALTH_STYLES = {
    "on_track": "pcc-status pcc-status-success",
    "at_risk": "pcc-status pcc-status-warning",
    "delayed": "pcc-status pcc-status-danger",
    "critical": "pcc-status pcc-status-danger",
}


@register.filter
def lifecycle_label(value):
    from apps.projects.models import LifecycleStatus

    return LifecycleStatus(value).label if value in LifecycleStatus.values else "—"


@register.filter
def lifecycle_style(value):
    return _LIFECYCLE_STYLES.get(value, "pcc-status pcc-status-neutral")


@register.filter
def health_label(value):
    from apps.projects.models import HealthStatus

    return HealthStatus(value).label if value in HealthStatus.values else "—"


@register.filter
def health_style(value):
    return _HEALTH_STYLES.get(value, "pcc-status pcc-status-neutral")


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
        "pending": "Menunggu keputusan",
        "approved": "Disetujui",
        "rejected": "Ditolak",
        "cancelled_request": "Dibatalkan",
        "skipped": "Tidak diperlukan",
        "draft": "Draf",
        "submitted": "Diajukan",
        "under_review": "Sedang ditinjau",
        "accepted": "Diterima",
        "applied": "Diterapkan",
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


@register.filter
def dict_get(mapping, key):
    """Ambil nilai dict dengan kunci dinamis di template."""
    try:
        return mapping.get(key, "")
    except AttributeError:
        return ""


@register.filter
def project_type_label(value):
    from apps.projects.models import ProjectType

    try:
        return ProjectType(value).label
    except ValueError:
        return value or "—"
