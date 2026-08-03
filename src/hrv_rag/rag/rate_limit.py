"""
rate_limit.py — Staying inside the Gemini API quota.

The free tier allows only a handful of requests per minute. Evaluation needs one
call per segment, so a batch run hits that ceiling within seconds and fails with
HTTP 429 partway through — losing every call already paid for in that run.

Two protections are combined:

1. **Proactive pacing.** A sliding window of recent request times; when the window
   is full, the next call waits until the oldest one ages out. This keeps the run
   under quota instead of discovering the limit by being rejected.

2. **Reactive retry.** If a 429 arrives anyway — quotas are also enforced per day
   and per token count, not only per minute — the call is retried using the delay
   the API itself suggests, with exponential backoff as a fallback.

The alternative, catching 429 and giving up, would waste an entire partial run. At
five requests per minute a 293-segment evaluation takes about an hour, so losing
one at minute fifty is expensive.
"""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

#: Pulls the server-suggested wait out of a 429 message, e.g. "retry in 28.5s".
_RETRY_DELAY = re.compile(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)")
_RETRY_IN = re.compile(r"retry in (\d+(?:\.\d+)?)s")


class RateLimiter:
    """Sliding-window limiter: at most `max_per_minute` calls in any 60 seconds."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._times: deque[float] = deque()

    def wait(self) -> float:
        """
        Block until another request is allowed. Returns how long it waited.

        The window is measured against the OLDEST call still inside it, rather than
        by sleeping a fixed interval between calls. That way a burst is allowed to
        proceed at full speed until the quota is genuinely exhausted.
        """
        waited = 0.0
        while True:
            now = time.monotonic()
            while self._times and now - self._times[0] >= 60.0:
                self._times.popleft()

            if len(self._times) < self.max_per_minute:
                self._times.append(now)
                return waited

            # Half a second of slack, because the server's clock is not ours.
            sleep_for = 60.0 - (now - self._times[0]) + 0.5
            time.sleep(sleep_for)
            waited += sleep_for


def _suggested_delay(message: str) -> float | None:
    """Read the wait time the API asked for, if it gave one."""
    for pattern in (_RETRY_DELAY, _RETRY_IN):
        match = pattern.search(message)
        if match:
            return float(match.group(1))
    return None


def call_with_retry(fn: Callable[[], T], max_attempts: int = 4,
                    base_delay: float = 30.0) -> T:
    """
    Run `fn`, retrying when the API reports the quota is exhausted.

    Only 429 is retried. Other errors — a bad schema, an invalid key, a malformed
    prompt — will not fix themselves by waiting, and retrying them would merely
    delay a failure that needs to be seen.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:                     # noqa: BLE001
            message = str(exc)
            if "429" not in message and "RESOURCE_EXHAUSTED" not in message:
                raise
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Quota still exhausted after {max_attempts} attempts. "
                    f"Consider a smaller sample, a model with a higher free "
                    f"limit, or enabling billing. Original error: {message[:200]}"
                ) from exc

            delay = _suggested_delay(message) or base_delay * attempt
            print(f"    [quota reached, waiting {delay:.0f}s "
                  f"— attempt {attempt}/{max_attempts}]")
            time.sleep(delay + 1.0)

    raise RuntimeError("unreachable")
