from datetime import datetime, timedelta, timezone
from functools import lru_cache
from secrets import token_urlsafe
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings
from app.core.errors import APIError

password_hasher = PasswordHash.recommended()
ISSUER = "outreach-backend"
AUDIENCE = "outreach-api"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


@lru_cache
def dummy_hash() -> str:
    return hash_password(token_urlsafe(32))


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        verified = password_hasher.verify(password, encoded or dummy_hash())
        return verified and encoded is not None
    except (ValueError, UnknownHashError):
        return False


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
            "iss": ISSUER,
            "aud": AUDIENCE,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> UUID:
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
            raise ValueError("Invalid timestamps")
        if claims["exp"] <= claims["iat"]:
            raise ValueError("Invalid lifetime")
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as exc:
        raise APIError(401, "invalid_token", "Invalid or expired access token") from exc
