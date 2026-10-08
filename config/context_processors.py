def settings(request):
    """Expose Django settings ke template (mis. threshold progress)."""
    from django.conf import settings as s
    from django.utils import timezone

    return {"settings": s, "workspace_date": timezone.localdate()}
