"""Cache-backed fixed-window request throttling for expensive endpoints."""

import time

from django.core.cache import cache


def is_rate_limited(
    *,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> bool:
    if limit <= 0:
        return False
    bucket = int(time.time()) // window_seconds
    key = f"matches-rate:{scope}:{identity}:{bucket}"
    if cache.add(key, 1, timeout=window_seconds + 1):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds + 1)
        return False
    return count > limit
