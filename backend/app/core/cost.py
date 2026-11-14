"""Dollars paid for model calls, counted per thread (R1b-4-2). An adapter that pays for a call
charges it here; a stage reads `spent()` before and after its call on the same thread
(ingest/timing.py, the identify probe), so a call on another thread never lands in its trace."""

import threading

_local = threading.local()


def charge(usd: float) -> None:
    _local.usd = spent() + usd


def spent() -> float:
    """What this thread has been charged so far."""
    return getattr(_local, "usd", 0.0)
