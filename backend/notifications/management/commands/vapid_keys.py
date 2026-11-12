"""Make the web push key pair (once per app). Changing it later turns everyone's notifications off until they turn them on again.

    python manage.py vapid_keys >> .env     # redirect it, so the private key is never shown on screen
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Generate VAPID keys for web push (prints the two env lines)."

    def handle(self, *args, **opts):
        key = ec.generate_private_key(ec.SECP256R1())
        private = b64(key.private_numbers().private_value.to_bytes(32, "big"))
        public = b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        self.stdout.write(f"VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}")
