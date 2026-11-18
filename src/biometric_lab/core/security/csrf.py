"""CSRF tokens bound to a session id (SYSTEM_DESIGN.md section 5.6).

A token is a signed payload containing the session id. On a state-changing request the
``X-CSRF-Token`` header must carry a token whose embedded session id matches the caller's
session cookie.
"""

from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer

_SALT = "biometric-lab-csrf"


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_SALT)


def issue_token(secret: str, session_id: str) -> str:
    return _serializer(secret).dumps({"sid": session_id})


def verify_token(secret: str, token: str, session_id: str, *, max_age: int = 86400) -> bool:
    try:
        data = _serializer(secret).loads(token, max_age=max_age)
    except BadSignature:
        return False
    return isinstance(data, dict) and data.get("sid") == session_id
