"""Small, signed remember-me tokens for the demonstration login."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

REMEMBER_LIFETIME_SECONDS = 14 * 24 * 60 * 60


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_remember_token(
    username: str,
    secret: str,
    *,
    now: int | None = None,
    lifetime_seconds: int = REMEMBER_LIFETIME_SECONDS,
) -> str:
    """Return a signed token containing only the username and expiry."""
    issued_at = int(time.time() if now is None else now)
    payload = _encode(
        json.dumps(
            {"user": username, "exp": issued_at + lifetime_seconds},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signature = _encode(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def validate_remember_token(
    token: str | None,
    username: str,
    secret: str,
    *,
    now: int | None = None,
) -> bool:
    """Validate signature, account binding, and expiry without exposing the secret."""
    if not token or token.count(".") != 1:
        return False
    payload, supplied_signature = token.split(".", 1)
    expected_signature = _encode(
        hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False
    try:
        claims = json.loads(_decode(payload).decode("utf-8"))
        expires_at = int(claims["exp"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    current_time = int(time.time() if now is None else now)
    return hmac.compare_digest(str(claims.get("user", "")), username) and expires_at > current_time
