"""Background jobs (the `Runner` port): one worker thread, jobs in the order given. One at a
time keeps memory bounded: reading a building model holds about 1 GB until the process ends
(app/adapters/ifc_model/objects.py)."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


class ThreadRunner:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")

    def submit(self, job: Callable[[], None]) -> None:
        self._pool.submit(job)

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=True)


class InlineRunner:
    """Runs each job at once, in the caller's thread: for the CLI and tests."""

    def submit(self, job: Callable[[], None]) -> None:
        job()

    def close(self) -> None:
        return None
