"""
rate_limit.py — Staying inside the Gemini API quota.

The free tier allows only a handful of requests per minute. Evaluation needs one
call per segment, so a batch run hits that ceiling within seconds and fails with
HTTP 429 partway through — losing every call already paid for in that run.

Two protections are combined:

1. **Proactive pacing.** A sliding window of recent request times; when the window
   is full, the next call waits until the oldest one ages out. This keeps the run
   under quota instead of discovering the limit by being rejected.

2. **Reactive retry.** Two kinds of failure are worth retrying, and only these two:

   - **429, quota exhausted.** Quotas are enforced per day and per token count as
     well as per minute, so pacing alone cannot prevent every rejection. The retry
     uses the delay the API itself suggests.
   - **5xx, server-side trouble.** A 503 means the model is temporarily overloaded
     at Google's end; nothing about the request is wrong and it will usually succeed
     shortly afterwards. Treating it as fatal would throw away an entire batch run
     because of a passing spike.

   Everything else fails immediately, because waiting will not fix it.

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

#: HTTP statuses worth retrying. 429 is quota; the 5xx family is transient trouble
#: on the server side. A 400 or 401 would never be fixed by waiting.
#:
#: The last group covers a self-hosted model: a rented GPU instance can refuse
#: connections for a few seconds while it wakes, and the proxy in front of it can
#: drop a connection mid-request. Both clear on their own, and treating them as
#: fatal would throw away a batch run for a hiccup. An authentication failure or a
#: missing model still fails immediately, because waiting will not fix those.
_RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "500", "502", "503", "504",
              "UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED",
              "ConnectError", "ConnectTimeout", "RemoteProtocolError")

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


def call_with_retry(fn: Callable[[], T], max_attempts: int = 5,
                    base_delay: float = 15.0,
                    is_retryable: Callable[[Exception], bool] | None = None) -> T:
    """
    Run `fn`, retrying quota rejections and transient server errors.

    Errors that waiting cannot fix — a bad schema, an invalid key, a malformed
    prompt — are raised immediately, because retrying them would only delay a
    failure that needs to be seen.

    Server errors back off faster than quota errors. A 503 usually clears within
    seconds, whereas a quota reset can take a minute, so the two are paced
    differently instead of sharing one delay.

    `is_retryable` lets a caller decide structurally instead of by looking for
    substrings. The Gemini SDK only exposes its status inside prose, so matching
    text is the best available there. HTTP callers can do better, and must: a
    self-hosted instance is reached at an arbitrary port, and a URL like
    `http://host:11503/...` carries "503" inside an error message that has nothing
    to do with a server being busy. Substring matching would then retry a fatal
    401 five times across four minutes before reporting the real problem.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:                     # noqa: BLE001
            message = str(exc)
            retry = (is_retryable(exc) if is_retryable is not None
                     else any(code in message for code in _RETRYABLE))
            if not retry:
                raise
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Still failing after {max_attempts} attempts. "
                    f"Original error: {message[:200]}"
                ) from exc

            is_quota = "429" in message or "RESOURCE_EXHAUSTED" in message
            if is_quota:
                delay = _suggested_delay(message) or base_delay * 2 * attempt
                label = "quota reached"
            else:
                # Exponential backoff for server-side trouble: 15s, 30s, 60s, 120s.
                delay = base_delay * (2 ** (attempt - 1))
                label = "server busy"

            print(f"    [{label}, waiting {delay:.0f}s "
                  f"— attempt {attempt}/{max_attempts}]")
            time.sleep(delay + 1.0)

    raise RuntimeError("unreachable")
