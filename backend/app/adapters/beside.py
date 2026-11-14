"""Two independent reads of one sheet at the same time (brief r8 BS: the Carbon calls of a raster
sheet used to run one after another, 44 s on a photo, 45 s on a scanned PDF).

`beside(here, there)` runs `there` on a worker thread while `here` runs on the calling thread and
returns both results, in that order, whichever finishes first. What `there`'s calls cost is
charged to the calling thread (app/core/cost.py counts per thread), also when either one fails.
It always waits for `there` before it returns or raises, so nothing is left running."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.core import cost


def beside[A, B](here: Callable[[], A], there: Callable[[], B]) -> tuple[A, B]:
    spent = [0.0]

    def run() -> B:
        before = cost.spent()
        try:
            return there()
        finally:
            spent[0] = cost.spent() - before

    pool = ThreadPoolExecutor(1, thread_name_prefix="beside")
    try:
        future = pool.submit(run)
        first = here()
    finally:
        pool.shutdown(wait=True)
        cost.charge(spent[0])
    return first, future.result()
