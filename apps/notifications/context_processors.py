def notifications(request):
    """Expose the header bell unread count on every page."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_notification_count": 0}
    from .services import unread_count

    return {"unread_notification_count": unread_count(user)}
