from rest_framework.permissions import BasePermission

from accounts.services import is_unlocked, touch


class SignedIn(BasePermission):
    message = "Sign in to continue."
    code = "signed_out"

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class Unlocked(SignedIn):
    """Signed in AND unlocked with Face ID or PIN recently. Money and settings endpoints use this."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not is_unlocked(request):
            self.message, self.code = "Unlock SpenDrip with Face ID or your PIN.", "locked"
            return False
        touch(request)
        return True
