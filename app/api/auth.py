"""Reusable authentication and authorization dependencies.

* ``get_current_user``: requires a valid access token (``Authorization: Bearer ...``).
* ``require_role(...)``: additionally requires one of the given roles (403 otherwise).

Policy: every /api/v1 resource route requires a user; viewers may only read (GET), so each
write route also declares ``AdminOnly``. tests/test_auth_api.py checks every write route.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.api.deps import AuthServiceDep
from app.core.rate_limit import SlidingWindowRateLimiter
from app.models import User, UserRole
from app.services.errors import PermissionDeniedError

API_PREFIX = "/api/v1"
LOGIN_PATH = f"{API_PREFIX}/auth/login"

# tokenUrl powers the "Authorize" button in /docs (OAuth2 password flow).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=LOGIN_PATH)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], auth: AuthServiceDep
) -> User:
    return await auth.user_from_access_token(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: the current user must have one of ``roles``."""
    allowed = frozenset(roles)

    async def check_role(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError("Your role does not allow this operation")
        return user

    return check_role


AdminOnly = Depends(require_role(UserRole.ADMIN))

LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 60


def new_login_rate_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)


async def limit_login_attempts(request: Request) -> None:
    """At most 10 login attempts per client IP per minute (in-process, see app/core/rate_limit).

    Behind Render's proxy the client IP comes from X-Forwarded-For, so Uvicorn must run with
    --proxy-headers (set up with the deploy); otherwise every client shares the proxy's IP.
    """
    limiter: SlidingWindowRateLimiter = request.app.state.login_rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    retry_after = limiter.hit(client_ip)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, try again later",
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )
