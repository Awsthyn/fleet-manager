from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole
from app.schemas.common import ReadModel


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int = Field(description="Access token lifetime in seconds.")


class TokenPairResponse(AccessTokenResponse):
    """OAuth2 token response (access_token + token_type) plus a refresh token."""

    refresh_token: str = Field(description="Use it with POST /auth/refresh; valid for 7 days.")
    refresh_expires_in: int = Field(description="Refresh token lifetime in seconds.")


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


class UserRead(ReadModel):
    """The authenticated user. Never includes the password hash."""

    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
