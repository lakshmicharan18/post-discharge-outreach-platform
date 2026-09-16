from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.models.entities import Role
from app.schemas.entities import HospitalResponse, UserResponse


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        try:
            # Syntax validation supports the reserved .test addresses used by our seed.
            return validate_email(
                value.strip(), check_deliverability=False, test_environment=True
            ).normalized.lower()
        except EmailNotValidError as exc:
            raise ValueError("Invalid email address") from exc


class LoginRequest(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=128)


class UserCreate(EmailInput):
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class CurrentUserResponse(UserResponse):
    hospital: HospitalResponse | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: CurrentUserResponse
