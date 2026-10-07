def settings(request):
    """Expose Django settings ke template (mis. threshold progress)."""
    from django.conf import settings as s

    return {"settings": s}