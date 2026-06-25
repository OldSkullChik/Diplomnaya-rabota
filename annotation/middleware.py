from django.conf import settings
from django.shortcuts import render

from .maintenance import read_maintenance_state


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self.is_exempt(request.path_info):
            return self.get_response(request)

        state = read_maintenance_state()
        if not state["enabled"]:
            return self.get_response(request)

        response = render(request, "maintenance.html", {"maintenance": state}, status=503)
        response["Retry-After"] = str(settings.MAINTENANCE_RETRY_AFTER)
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def is_exempt(path):
        return any(path.startswith(prefix) for prefix in settings.MAINTENANCE_EXEMPT_PATHS)
