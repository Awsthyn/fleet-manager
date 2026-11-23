"""In-process sliding-window rate limiter for login attempts.

State lives in this process's memory. That is enough on Render Free, which runs a single
instance of the API: every request reaches the same process and therefore the same counters.
With several instances (or workers) each would count separately and the effective limit would
multiply; a shared store such as Redis would then be needed. A restart (Render sleeps after 15
idle minutes) also resets the counters, which is acceptable for this purpose.
"""

import time
from collections import deque
from collections.abc import Callable

# Forget idle clients once this many keys are tracked, to keep memory bounded (512 MB plan).
_MAX_TRACKED_KEYS = 10_000


class SlidingWindowRateLimiter:
    def __init__(
        self,
        max_attempts: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, deque[float]] = {}

    def hit(self, key: str) -> float | None:
        """Record an attempt for ``key``.

        Returns None if it is allowed, or the seconds to wait if the limit is exceeded
        (blocked attempts are not recorded, so waiting the returned time always works).
        """
        now = self._clock()
        attempts = self._attempts.setdefault(key, deque())
        while attempts and attempts[0] <= now - self.window_seconds:
            attempts.popleft()
        if len(attempts) >= self.max_attempts:
            return attempts[0] + self.window_seconds - now
        attempts.append(now)
        if len(self._attempts) > _MAX_TRACKED_KEYS:
            self._prune(now)
        return None

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [key for key, attempts in self._attempts.items() if attempts[-1] <= cutoff]
        for key in stale:
            del self._attempts[key]
