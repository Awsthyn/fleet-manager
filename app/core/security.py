"""Password hashing and JWT handling. Pure functions: no HTTP, no database."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

# Argon2id with pwdlib's recommended parameters (the approach in FastAPI's security docs).
_password_hash = PasswordHash.recommended()

# Verified against when the email is unknown, so a login attempt takes about the same time
# whether or not the account exists (no user enumeration through response timing).
_DUMMY_HASH = _password_hash.hash("dummy-password-for-constant-time-checks")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    """Check ``password`` against ``hashed``; with ``hashed=None`` burn the same time and fail."""
    if hashed is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, hashed)


class TokenError(Exception):
    """The token is malformed, has a bad signature, is of the wrong type or has expired."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_in: int  # seconds


def create_token(
    user_id: int, token_type: TokenType, settings: Settings, now: datetime | None = None
) -> IssuedToken:
    issued_at = now or datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        if token_type == "access"  # noqa: S105 - a token kind, not a password
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    claims: dict[str, object] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "jti": uuid4().hex,
    }
    # PyJWT types ``key`` with cryptography's key classes, which are not installed (HS* only),
    # so pyright sees part of the signature as Unknown; the str secret we pass is fully typed.
    token = jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return IssuedToken(token=token, expires_in=int(lifetime.total_seconds()))


def decode_token(token: str, expected_type: TokenType, settings: Settings) -> int:
    """Validate ``token`` and return the user id it was issued for."""
    try:
        claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType] - see create_token
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "type", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc

    # A refresh token must never work as an access token, nor the other way around.
    if claims.get("type") != expected_type:
        raise TokenError("Invalid token type")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise TokenError("Invalid token")
    return int(subject)
