from django.utils.cache import patch_vary_headers


class PrivateJsonNoStoreMiddleware:
    """Prevent authenticated API payloads from being reused across sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            getattr(request, "user", None)
            and request.user.is_authenticated
            and response.get("Content-Type", "").startswith("application/json")
        ):
            response["Cache-Control"] = "private, no-store, no-cache, max-age=0, must-revalidate"
            response["Pragma"] = "no-cache"
            patch_vary_headers(response, ("Cookie",))
        return response
