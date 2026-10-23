"""Bind the acting user to revision capture for the duration of a request."""


class RevisionActorMiddleware:
    def __init__(self, get_response):
        from .revisions import clear_request_state, set_request_state

        self.get_response = get_response
        self._set_request_state = set_request_state
        self._clear_request_state = clear_request_state

    def __call__(self, request):
        self._set_request_state(request.user)
        try:
            return self.get_response(request)
        finally:
            self._clear_request_state()
