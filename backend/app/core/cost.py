"""Dollars paid for model calls, counted per thread (R1b-4-2). An adapter that pays for a call
charges it here; a stage takes `mark()` before its call and `since(mark)` after it on the same
thread (ingest/timing.py, the identify probe), so a call on another thread never lands in its
trace.

The count is kept in whole pico-dollars, so what a stage paid is exact whatever the thread was
charged before: with dollars as a float, 0.002 + 0.001 charged after 0.0123 read back as
0.0030000000000000027 (review-311). Pico, not the spend guard's micro (app/core/spend.py): a
trace shows each call's cost, and a Decisions call of 0.0003151 USD would read 0.000315."""

import threading

PICO = 10**12  # per dollar; any total under 9,000 USD stays an exact float when multiplied

_local = threading.local()


def charge(usd: float) -> None:
    _local.pico = mark() + round(usd * PICO)


def mark() -> int:
    """What this thread has been charged so far, in pico-dollars: `since`'s argument."""
    return getattr(_local, "pico", 0)


def since(before: int) -> float:
    """The dollars this thread was charged since `before` (a `mark()`)."""
    return (mark() - before) / PICO
