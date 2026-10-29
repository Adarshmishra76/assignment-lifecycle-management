from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.user import User
import jwt


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    return get_current_user(authorization=authorization, db=db)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token subject")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


def require_roles(*roles: str):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("Insufficient role permissions")
        return user

    return _checker
