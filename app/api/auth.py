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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def limit_login_attempts(request: Request) -> None:
    """At most 10 failed login attempts per client IP per minute (in-process, see
    app/core/rate_limit).

    Every attempt reserves a slot when it arrives (concurrent guesses cannot slip past the
    limit while they are being checked); a successful login gives it back with
    ``refund_login_attempt``. Only failures count, so the dashboard's server, which signs in
    every demo visitor from the same address, is not throttled by legitimate logins.

    Behind Render's proxy the client IP comes from X-Forwarded-For, resolved by Uvicorn's proxy
    headers support against the trusted proxies in app/core/proxies.py (see app/scripts/start.py).
    """
    limiter: SlidingWindowRateLimiter = request.app.state.login_rate_limiter
    retry_after = limiter.hit(_client_ip(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, try again later",
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )


def refund_login_attempt(request: Request) -> None:
    """A login succeeded: give back the slot ``limit_login_attempts`` reserved for it."""
    limiter: SlidingWindowRateLimiter = request.app.state.login_rate_limiter
    limiter.refund(_client_ip(request))
