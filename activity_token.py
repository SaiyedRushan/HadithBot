"""The session token the game (Activity) sends with every request.

Inside Discord's iframe there are no cookies, so after the Discord sign-in the
API hands the game a signed token. It seals who the player is and which
channel the game was opened in, so later requests can't claim another channel.
Format, as in MugUp's ``lib/discord/signed-payload.ts``:
``v1.<base64url json>.<base64url HMAC-SHA256 over "v1.<payload>">``.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

VERSION = "v1"
TTL_SECONDS = 2 * 60 * 60


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, message: str) -> str:
    return _b64(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest())


def mint(secret: str, claims: dict, now: Optional[float] = None) -> str:
    body = dict(claims, exp=int((now or time.time()) + TTL_SECONDS))
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{VERSION}.{payload}.{_sign(secret, f'{VERSION}.{payload}')}"


def verify(secret: str, token: str, now: Optional[float] = None) -> Optional[dict]:
    """The claims, or None for anything forged, malformed or expired."""
    try:
        version, payload, signature = token.split(".")
    except (AttributeError, ValueError):
        return None
    if version != VERSION:
        return None
    if not hmac.compare_digest(signature, _sign(secret, f"{version}.{payload}")):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(claims, dict) or claims.get("exp", 0) < (now or time.time()):
        return None
    return claims
