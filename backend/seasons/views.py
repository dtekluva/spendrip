from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Season


class CurrentSeason(APIView):
    """Which outfit Kobo wears right now. Public, because Kobo also appears before sign-in."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        s = Season.current()
        resp = Response({"outfit": s.outfit, "until": s.ends_on} if s else {"outfit": None, "until": None})
        resp["Cache-Control"] = "public, max-age=300"  # a change in the admin reaches everyone within 5 minutes
        return resp
