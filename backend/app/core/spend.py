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
in memory: a restart starts it at 0, and each worker process has its own.

`cost.charge` stays the per-thread counter the traces read. This ledger is charged at the paid
call itself, once: the raster reader charges its worker threads' costs again to the calling
thread for that thread's trace (app/adapters/raster/__init__.py), which would count them twice.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

HOUR_S = 3600.0
MICRO = 1_000_000  # dollars are kept in whole micro-dollars, so sums are exact


def _micro(usd: float) -> int:
    return round(usd * MICRO)


def _usd(micro: int) -> str:
    return f"{micro / MICRO:.2f}"


class SpendGuard:
    def __init__(
        self,
        total_usd: float | None = None,
        per_hour_usd: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._total = None if total_usd is None else _micro(total_usd)
        self._hourly = None if per_hour_usd is None else _micro(per_hour_usd)
        self._clock = clock
        self._lock = threading.Lock()
        self._spent = 0
        self._by_what: dict[str, int] = {}
        self._recent: deque[tuple[float, int]] = deque()  # (time, micro-dollars) of the last hour
        self._in_hour = 0

    @property
    def limited(self) -> bool:
        """Whether a limit is set at all (else the ledger only counts)."""
        return self._total is not None or self._hourly is not None

    @property
    def spent_usd(self) -> float:
        with self._lock:
            return self._spent / MICRO

    def spent_by(self) -> dict[str, float]:
        """Dollars charged so far, by the `what` each charge named."""
        with self._lock:
            return {what: micro / MICRO for what, micro in self._by_what.items()}

    def exhausted(self) -> str | None:
        """Why no Gemini call may start now, or None."""
        with self._lock:
            self._forget()
            if self._total is not None and self._spent >= self._total:
                return (
                    f"Gemini budget used up ({_usd(self._spent)} USD spent, "
                    f"GEMINI_BUDGET_USD={_usd(self._total)})"
                )
            if self._hourly is not None and self._in_hour >= self._hourly:
                return (
                    f"Gemini hourly budget used up ({_usd(self._in_hour)} USD in the last hour, "
                    f"GEMINI_BUDGET_USD_PER_HOUR={_usd(self._hourly)})"
                )
            return None

    def remaining(self) -> float | None:
        """Dollars left before the nearer limit (0 when used up); None when no limit is set."""
        with self._lock:
            self._forget()
            left = [
                limit - used
                for limit, used in ((self._total, self._spent), (self._hourly, self._in_hour))
                if limit is not None
            ]
            return max(0, min(left)) / MICRO if left else None

    def charge(self, cost_usd: float, what: str = "gemini") -> None:
        """Counts a paid reply's dollars; `what` names the caller in `spent_by`."""
        micro = _micro(cost_usd)
        with self._lock:
            self._spent += micro
            self._by_what[what] = self._by_what.get(what, 0) + micro
            if self._hourly is not None:
                self._recent.append((self._clock(), micro))
                self._in_hour += micro

    def _forget(self) -> None:
        """Drops the spend that is more than an hour old from the hourly sum."""
        cutoff = self._clock() - HOUR_S
        while self._recent and self._recent[0][0] <= cutoff:
            self._in_hour -= self._recent.popleft()[1]
