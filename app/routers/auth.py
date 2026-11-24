from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.api.auth import CurrentUser, limit_login_attempts, refund_login_attempt
from app.api.deps import AuthServiceDep
from app.schemas.auth import AccessTokenResponse, RefreshRequest, TokenPairResponse, UserRead
from app.schemas.common import RATE_LIMITED, UNAUTHORIZED, VALIDATION

router = APIRouter(prefix="/auth", tags=["auth"], responses={**VALIDATION, **UNAUTHORIZED})


@router.post(
    "/login",
    summary="Log in (OAuth2 password flow)",
    dependencies=[Depends(limit_login_attempts)],
    responses={**RATE_LIMITED},
)
async def login(
    request: Request, auth: AuthServiceDep, form: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> TokenPairResponse:
    """Form fields `username` (the email) and `password`. Returns a 15-minute access token and
    a 7-day refresh token. Limited to 10 failed attempts per minute per IP."""
    pair = await auth.login(form.username, form.password)
    refund_login_attempt(request)
    return TokenPairResponse(
        access_token=pair.access.token,
        expires_in=pair.access.expires_in,
        refresh_token=pair.refresh.token,
        refresh_expires_in=pair.refresh.expires_in,
    )


@router.post("/refresh", summary="Get a new access token")
async def refresh(auth: AuthServiceDep, body: RefreshRequest) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new access token."""
    issued = await auth.refresh(body.refresh_token)
    return AccessTokenResponse(access_token=issued.token, expires_in=issued.expires_in)


@router.get("/me", summary="Current user")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
