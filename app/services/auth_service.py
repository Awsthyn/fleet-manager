from dataclasses import dataclass

from app.core.config import Settings
from app.core.security import (
    IssuedToken,
    TokenError,
    TokenType,
    create_token,
    decode_token,
    verify_password,
)
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.errors import AuthenticationError

INVALID_CREDENTIALS = "Incorrect email or password"


@dataclass(frozen=True)
class TokenPair:
    access: IssuedToken
    refresh: IssuedToken


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self.users = users
        self.settings = settings

    async def login(self, email: str, password: str) -> TokenPair:
        """Exchange credentials for an access + refresh token pair.

        Unknown email, wrong password and inactive account all give the same error, so the
        response does not reveal which accounts exist.
        """
        user = await self.users.get_by_email(normalize_email(email))
        password_ok = verify_password(password, user.hashed_password if user else None)
        if user is None or not password_ok or not user.is_active:
            raise AuthenticationError(INVALID_CREDENTIALS)
        return TokenPair(
            access=create_token(user.id, "access", self.settings),
            refresh=create_token(user.id, "refresh", self.settings),
        )

    async def refresh(self, refresh_token: str) -> IssuedToken:
        """Issue a new access token from a valid refresh token of an active user."""
        user = await self._user_from_token(refresh_token, "refresh")
        return create_token(user.id, "access", self.settings)

    async def user_from_access_token(self, access_token: str) -> User:
        return await self._user_from_token(access_token, "access")

    async def _user_from_token(self, token: str, token_type: TokenType) -> User:
        try:
            user_id = decode_token(token, token_type, self.settings)
        except TokenError as exc:
            raise AuthenticationError(str(exc)) from exc
        user = await self.users.get(user_id)
        # A deleted or deactivated user's outstanding tokens stop working immediately.
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid token")
        return user
