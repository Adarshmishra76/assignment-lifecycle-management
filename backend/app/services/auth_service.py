from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError, ValidationAppError
from app.core.ids import next_public_id
from app.core.lifecycle import ROLES
from app.core.security import create_access_token, hash_password, verify_password
from app.models.learner import Learner
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.audit import record_audit

OPEN_ROLES = {"learner"}


def register_user(db: Session, payload: RegisterRequest, actor: User | None) -> User:
    role = payload.role
    if role not in ROLES:
        raise ValidationAppError("Invalid role")
    if actor is None and role not in OPEN_ROLES:
        raise ValidationAppError("Only learner self-registration is allowed")
    if actor and actor.role != "platform_admin" and role in {"platform_admin"}:
        raise ValidationAppError("Only a platform administrator can create platform admins")
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise ConflictError("Email already registered")
    user = User(
        public_id=next_public_id(db, User, "USR"),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    if role == "learner":
        student_number = payload.student_number or user.public_id.replace("USR", "STU")
        if db.scalar(select(Learner).where(Learner.student_number == student_number)):
            raise ConflictError("Student number already exists")
        learner = Learner(
            public_id=next_public_id(db, Learner, "LRN", 7),
            user_id=user.id,
            student_number=student_number,
        )
        db.add(learner)
    record_audit(
        db,
        actor_id=actor.id if actor else user.id,
        entity_type="user",
        entity_id=user.id,
        action="register",
        to_state=role,
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, payload: LoginRequest) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    token = create_access_token(str(user.id), extra={"role": user.role})
    return user, token


def bootstrap_admin(db: Session, email: str, password: str) -> User | None:
    existing = db.scalar(select(User).where(User.role == "platform_admin"))
    if existing:
        return existing
    user = User(
        public_id="USR-000001",
        email=email.lower(),
        password_hash=hash_password(password),
        full_name="Platform Administrator",
        role="platform_admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
