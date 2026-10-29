from datetime import timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.time import utcnow

password_hasher = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    return password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return password_hasher.verify(plain, hashed)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": utcnow() + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": utcnow(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
