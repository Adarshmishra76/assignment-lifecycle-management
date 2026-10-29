from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.lifecycle import ROLES
from app.schemas.common import ORMModel


# EmailStr rejects reserved TLDs such as .local, which the demo accounts use.
EmailAddress = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


class RegisterRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = "learner"
    student_number: str | None = None

    def validate_role(self) -> str:
        if self.role not in ROLES:
            raise ValueError("Invalid role")
        return self.role


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    public_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
