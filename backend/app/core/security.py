import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + settings.ACCESS_TOKEN_TTL_SECONDS,
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        settings.JWT_SECRET.encode(),
        payload_part.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_part}.{signature}"


def verify_access_token(token: str) -> str | None:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(
        settings.JWT_SECRET.encode(),
        payload_part.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except (json.JSONDecodeError, ValueError):
        return None

    if payload.get("exp", 0) < time.time():
        return None

    user_id = payload.get("sub")
    return str(user_id) if user_id else None
