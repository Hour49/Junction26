"""The Gemini spend guard (GEMINI_BUDGET_USD, GEMINI_BUDGET_USD_PER_HOUR; deploy runbook section 4).

One ledger per process, `app.composition.spend_guard(settings)`. Any code that pays for a Gemini
call uses it, ours or not (an agent calling Gemini's OpenAI-compatible endpoint too):

    guard = spend_guard(settings)
    if why := guard.exhausted():   # before the call: a reason to show, or None
        ...                        # don't call; say `why`
    ...                            # the call
    guard.charge(cost_usd, "agent chat")   # after a paid reply, its measured cost

`remaining()` is the dollars left before a limit (None: no limit). Our Gemini clients (room
reader, Decisions, describer) do exactly this; when refused they raise their own error, so each
step takes the path it already has for a failed call ("not available", the answer left unknown)
and its note says why. Replies the steps have cached cost nothing and are still served: a client
is only called on a cache miss. Calls already running when the limit is reached finish and are
charged, so the total can pass the limit by the calls in flight at that moment. The ledger lives
in memory by default (`MemorySpend`: a restart starts it at 0, each process has its own); with
SPEND_LEDGER_PATH it lives in a file (app/adapters/spend_file.py) that every process on it shares
and a restart keeps, the hourly window included (brief r8 BT: each auto-deploy restarts the app,
and the old and new copy run side by side for a few seconds).

`cost.charge` stays the per-thread counter the traces read. This ledger is charged at the paid
call itself, once: the raster reader charges its worker threads' costs again to the calling
thread for that thread's trace (app/adapters/raster/__init__.py), which would count them twice.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

HOUR_S = 3600.0
MICRO = 1_000_000  # dollars are kept in whole micro-dollars, so sums are exact


def _micro(usd: float) -> int:
    return round(usd * MICRO)


def _usd(micro: int) -> str:
    return f"{micro / MICRO:.2f}"


@dataclass(frozen=True)
class Spent:
    """What the ledger holds, in micro-dollars: the total, by caller, and the charges of the last
    hour as (clock time, micro-dollars)."""

    total: int = 0
    by_what: dict[str, int] = field(default_factory=dict[str, int])
    recent: tuple[tuple[float, int], ...] = ()


class SpendStore(Protocol):
    """Where the ledger is kept. `add` is atomic against every other writer of the same store
    (threads, and processes for a shared one) and drops the charges at or before `forget_at`."""

    def read(self) -> Spent: ...

    def add(self, micro: int, what: str, at: float, forget_at: float) -> Spent: ...


def added(spent: Spent, micro: int, what: str, at: float, forget_at: float) -> Spent:
    """`spent` with one more charge: what every store's `add` writes."""
    return Spent(
        total=spent.total + micro,
        by_what={**spent.by_what, what: spent.by_what.get(what, 0) + micro},
        recent=(*(c for c in spent.recent if c[0] > forget_at), (at, micro)),
    )


class MemorySpend:
    """The ledger in this process's memory (SPEND_LEDGER_PATH unset)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spent = Spent()

    def read(self) -> Spent:
        with self._lock:
            return self._spent

    def add(self, micro: int, what: str, at: float, forget_at: float) -> Spent:
        with self._lock:
            self._spent = added(self._spent, micro, what, at, forget_at)
            return self._spent


class SpendGuard:
    """`clock` times the hourly window: a store shared across processes and restarts needs the
    wall clock (time.time), which composition passes with it."""

    def __init__(
        self,
        total_usd: float | None = None,
        per_hour_usd: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        store: SpendStore | None = None,
    ) -> None:
        self._total = None if total_usd is None else _micro(total_usd)
        self._hourly = None if per_hour_usd is None else _micro(per_hour_usd)
        self._clock = clock
        self._store: SpendStore = MemorySpend() if store is None else store

    @property
    def limited(self) -> bool:
        """Whether a limit is set at all (else the ledger only counts)."""
        return self._total is not None or self._hourly is not None

    @property
    def spent_usd(self) -> float:
        return self._store.read().total / MICRO

    def spent_by(self) -> dict[str, float]:
        """Dollars charged so far, by the `what` each charge named."""
        return {what: micro / MICRO for what, micro in self._store.read().by_what.items()}

    def exhausted(self) -> str | None:
        """Why no Gemini call may start now, or None."""
        spent = self._store.read()
        in_hour = self._in_hour(spent)
        if self._total is not None and spent.total >= self._total:
            return (
                f"Gemini budget used up ({_usd(spent.total)} USD spent, "
                f"GEMINI_BUDGET_USD={_usd(self._total)})"
            )
        if self._hourly is not None and in_hour >= self._hourly:
            return (
                f"Gemini hourly budget used up ({_usd(in_hour)} USD in the last hour, "
                f"GEMINI_BUDGET_USD_PER_HOUR={_usd(self._hourly)})"
            )
        return None

    def remaining(self) -> float | None:
        """Dollars left before the nearer limit (0 when used up); None when no limit is set."""
        spent = self._store.read()
        left = [
            limit - used
            for limit, used in ((self._total, spent.total), (self._hourly, self._in_hour(spent)))
            if limit is not None
        ]
        return max(0, min(left)) / MICRO if left else None

    def charge(self, cost_usd: float, what: str = "gemini") -> None:
        """Counts a paid reply's dollars; `what` names the caller in `spent_by`."""
        now = self._clock()
        self._store.add(_micro(cost_usd), what, now, now - HOUR_S)

    def _in_hour(self, spent: Spent) -> int:
        """The spend of the last hour: an older charge no longer counts."""
        cutoff = self._clock() - HOUR_S
        return sum(micro for at, micro in spent.recent if at > cutoff)
