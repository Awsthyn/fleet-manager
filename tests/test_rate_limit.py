from app.core.rate_limit import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_limit_applies_per_key_and_window_slides() -> None:
    """Guards the limiter: rejects shared counters across IPs or a window that never frees up."""
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60, clock=clock)

    first_three = [limiter.hit("10.0.0.1") for _ in range(3)]
    fourth = limiter.hit("10.0.0.1")
    other_ip = limiter.hit("10.0.0.2")
    clock.now += 60
    after_window = limiter.hit("10.0.0.1")

    assert first_three == [None, None, None]
    assert fourth == 60
    assert other_ip is None
    assert after_window is None


def test_blocked_attempts_do_not_extend_the_wait() -> None:
    """Guards Retry-After honesty: rejects counting blocked attempts, which would extend the ban."""
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60, clock=clock)

    limiter.hit("ip")
    clock.now += 30
    retry_after = limiter.hit("ip")
    clock.now += 30

    assert retry_after == 30
    assert limiter.hit("ip") is None
