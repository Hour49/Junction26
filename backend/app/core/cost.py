"""Dollars paid for model calls, counted per thread (R1b-4-2). An adapter that pays for a call
charges it here; a stage takes `mark()` before its call and `since(mark)` after it on the same
thread (ingest/timing.py, the identify probe), so a call on another thread never lands in its
trace.

The count is kept in whole pico-dollars, so what a stage paid is exact whatever the thread was
charged before: with dollars as a float, 0.002 + 0.001 charged after 0.0123 read back as
0.0030000000000000027 (review-311). Pico, not the spend guard's micro (app/core/spend.py): a
trace shows each call's cost, and a Decisions call of 0.0003151 USD would read 0.000315."""

import threading
from collections.abc import Callable

PICO = 10**12  # per dollar; any total under 9,000 USD stays an exact float when multiplied

_local = threading.local()


def charge(usd: float) -> None:
    _local.pico = mark() + round(usd * PICO)


def mark() -> int:
    """What this thread has been charged so far, in pico-dollars: `since`'s argument."""
    return getattr(_local, "pico", 0)


def fail(count: int = 1) -> None:
    """A model call that got no answer (HTTP 429/5xx, a timeout, a reset): counted per thread
    like the dollars, so the ingest can tell a sheet read while the model failed from one read
    in full, and not keep the first as the file's reading for later uploads."""
    _local.failed = faults() + count


def faults() -> int:
    """How many calls have failed on this thread so far: `faults_since`'s argument."""
    return getattr(_local, "failed", 0)


def faults_since(before: int) -> int:
    return faults() - before


class Carry:
    """What a call run on another thread paid and saw fail, to hand back to the calling thread.

    `run(call)` on the worker thread records the dollars and failed calls of `call` (also when it
    raises); `hand_back()` on the caller adds them to the caller's own counts, so the stage that
    asked sees them (`beside`, and any helper that runs a read on a thread of its own)."""

    def __init__(self) -> None:
        self.usd = 0.0
        self.failed = 0

    def run[T](self, call: "Callable[[], T]") -> T:
        before, faulted = mark(), faults()
        try:
            return call()
        finally:
            self.usd, self.failed = since(before), faults_since(faulted)

    def hand_back(self) -> None:
        charge(self.usd)
        fail(self.failed)


def since(before: int) -> float:
    """The dollars this thread was charged since `before` (a `mark()`)."""
    return (mark() - before) / PICO
