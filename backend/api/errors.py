from rest_framework.response import Response
from rest_framework.views import exception_handler

from accounts.services import FlowError


def handle(exc, context):
    """Every error the app sees has the same shape: {"error": "<plain sentence>", "code": "<machine code>"}."""
    if isinstance(exc, FlowError):
        return Response({"error": exc.message, "code": exc.code}, status=exc.status)
    resp = exception_handler(exc, context)
    if resp is None:
        return None
    data = resp.data
    if isinstance(data, dict) and "detail" in data:
        code = getattr(data["detail"], "code", "error")
        if code in ("not_authenticated", "authentication_failed"):
            resp.data = {"error": "Sign in to continue.", "code": "signed_out"}
        else:
            resp.data = {"error": str(data["detail"]), "code": code}
    elif isinstance(data, dict):
        field, msgs = next(iter(data.items()))
        msg = msgs[0] if isinstance(msgs, list) else msgs
        resp.data = {"error": str(msg) if field == "non_field_errors" else f"{field}: {msg}", "code": "invalid", "fields": data}
    return resp
