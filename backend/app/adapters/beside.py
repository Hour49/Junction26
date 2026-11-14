"""Two independent reads of one sheet at the same time (brief r8 BS: the Carbon calls of a raster
sheet used to run one after another, 44 s on a photo, 45 s on a scanned PDF).

`beside(here, there)` runs `there` on a worker thread while `here` runs on the calling thread and
returns both results, in that order, whichever finishes first. What `there`'s calls cost is
charged to the calling thread (app/core/cost.py counts per thread). When `here` succeeds it waits
for `there`, and an error of `there` is raised on the calling thread.

When `here` fails, its error is raised at once (review-306 S1): `there` is cancelled if it has not
started, and is not waited for if it has; a call it has in flight runs to its end in the
background (the spend guard still counts it, the failed file's trace does not). Since nobody
reads its result then, an error it ends with is logged (review-306 S2)."""

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from app.core import cost

log = logging.getLogger(__name__)


def beside[A, B](here: Callable[[], A], there: Callable[[], B]) -> tuple[A, B]:
    spent = [0.0]

    def run() -> B:
        before = cost.spent()
        try:
            return there()
        finally:
            spent[0] = cost.spent() - before

    pool = ThreadPoolExecutor(1, thread_name_prefix="beside")
    future = pool.submit(run)
    try:
        first = here()
    except BaseException:
        future.cancel()  # not started yet: it never runs
        future.add_done_callback(_log_dropped)
        pool.shutdown(wait=False)
        if future.done() and not future.cancelled():
            cost.charge(spent[0])
        raise
    pool.shutdown(wait=True)
    cost.charge(spent[0])
    return first, future.result()


def _log_dropped(future: "Future[Any]") -> None:
    """The error of a read whose partner failed first: nobody reads it, so it is logged."""
    if future.cancelled():
        return
    error = future.exception()
    if error is not None:
        log.warning("a read beside a failed one also failed", exc_info=error)
