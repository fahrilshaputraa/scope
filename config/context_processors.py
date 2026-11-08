def _css_version():
    from django.conf import settings as s

    try:
        return int((s.BASE_DIR / "static" / "css" / "output.css").stat().st_mtime)
    except OSError:
        return 0


def settings(request):
    """Expose Django settings ke template (mis. threshold progress)."""
    from django.conf import settings as s
    from django.utils import timezone

    return {
        "settings": s,
        "workspace_date": timezone.localdate(),
        "css_version": _css_version(),
    }
