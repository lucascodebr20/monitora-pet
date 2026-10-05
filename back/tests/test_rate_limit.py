import unittest

from app.core.rate_limit import FailedAttemptLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FailedAttemptLimiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.limiter = FailedAttemptLimiter(max_failures=3, window_seconds=60, lock_seconds=30, max_lock_seconds=120, clock=self.clock)

    def test_locks_after_max_failures_and_releases_after_lock_period(self):
        self.assertEqual(self.limiter.record_failure("ip"), 0.0)
        self.assertEqual(self.limiter.record_failure("ip"), 0.0)
        self.assertEqual(self.limiter.record_failure("ip"), 30.0)
        self.assertEqual(self.limiter.seconds_locked("ip"), 30.0)
        self.clock.now += 31
        self.assertEqual(self.limiter.seconds_locked("ip"), 0.0)

    def test_lock_duration_doubles_until_the_cap(self):
        durations = []
        for _ in range(4):
            for _ in range(2):
                self.limiter.record_failure("ip")
            durations.append(self.limiter.record_failure("ip"))
            self.clock.now += durations[-1] + 1
        self.assertEqual(durations, [30.0, 60.0, 120.0, 120.0])

    def test_failures_outside_the_window_are_forgotten(self):
        self.limiter.record_failure("ip")
        self.limiter.record_failure("ip")
        self.clock.now += 61
        self.assertEqual(self.limiter.record_failure("ip"), 0.0)

    def test_success_resets_the_counter_and_origins_are_independent(self):
        self.limiter.record_failure("a")
        self.limiter.record_failure("a")
        self.limiter.reset("a")
        self.assertEqual(self.limiter.record_failure("a"), 0.0)
        self.assertEqual(self.limiter.seconds_locked("b"), 0.0)


if __name__ == "__main__":
    unittest.main()
