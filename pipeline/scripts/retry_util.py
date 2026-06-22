"""
retry_util.py
Tiny dependency-free retry-with-exponential-backoff helper for transient external-call
failures (PAGASA download, Claude advisory, Semaphore SMS). Pure + unit-testable —
`sleep` is injectable so tests don't actually wait.

A transient network error on any one call previously dropped a whole province's
advisory or SMS for the week; a couple of bounded retries recover most blips.
"""

import logging
import time
from typing import Callable, Iterable, Optional, Type, TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Iterable[Type[BaseException]] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    label: str = "call",
) -> T:
    """Call ``fn()``; on a listed exception, back off and retry up to ``attempts`` times.

    Delays are ``base_delay * 2**(n-1)`` capped at ``max_delay``. The final failure is
    re-raised unchanged. Exceptions not in ``exceptions`` propagate immediately.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    exc_tuple = tuple(exceptions)
    last: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except exc_tuple as e:
            last = e
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            log.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs",
                        label, attempt, attempts, e, delay)
            sleep(delay)
    assert last is not None
    raise last
