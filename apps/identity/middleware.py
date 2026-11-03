from .roles import _ACTIVE_ATTR, SESSION_KEY


class ActiveRoleMiddleware:
    """Pasang role aktif dari sesi ke ``request.user`` (PRD §4.3)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            chosen = request.session.get(SESSION_KEY)
            if chosen:
                setattr(user, _ACTIVE_ATTR, chosen)
        return self.get_response(request)
