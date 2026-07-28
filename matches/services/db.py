"""Small retry helper for transient SQLite write-lock contention."""

from collections.abc import Callable
import time
from typing import TypeVar

from django.db import OperationalError

ResultT = TypeVar("ResultT")


def retry_transient_db_lock(
    operation: Callable[[], ResultT],
    *,
    attempts: int = 3,
    initial_delay: float = 0.05,
) -> ResultT:
    """Retry only SQLite-style locked/busy failures, never other DB errors."""

    delay = initial_delay
    for attempt in range(attempts):
        try:
            return operation()
        except OperationalError as error:
            message = str(error).lower()
            is_transient = "locked" in message or "busy" in message
            if not is_transient or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")
