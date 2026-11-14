"""SPEND_LEDGER_PATH: the Gemini spend ledger (app/core/spend.py) in a JSON file, so a restart
(each auto-deploy) keeps the total and the hourly window, and two processes on the same file (the
old and the new copy during a deploy) share one ledger (brief r8 BT).

Every `add` holds an exclusive `flock` on `<path>.lock` while it reads, adds and writes, so no
charge is lost between processes or threads; the file is written to a temporary file beside it and
moved in with `os.replace`, so a reader never sees half a file and needs no lock. A missing file is
an empty ledger. An unreadable one is an error, not 0: a ledger that forgot its spend would lift
the caps."""

import fcntl
import json
import os
import tempfile
from pathlib import Path

from app.core.spend import Spent, added

SCHEMA = "spend_ledger_v1"


class FileSpend:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock_path = path.with_name(path.name + ".lock")
        path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> Spent:
        try:
            body = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Spent()
        if body.get("schema") != SCHEMA:
            raise ValueError(f"{self._path} is not a {SCHEMA} file")
        return Spent(
            total=int(body["total"]),
            by_what={str(what): int(micro) for what, micro in body["by_what"].items()},
            recent=tuple((float(at), int(micro)) for at, micro in body["recent"]),
        )

    def add(self, micro: int, what: str, at: float, forget_at: float) -> Spent:
        with self._lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # released when the file closes
            spent = added(self.read(), micro, what, at, forget_at)
            self._write(spent)
            return spent

    def _write(self, spent: Spent) -> None:
        body = {
            "schema": SCHEMA,
            "total": spent.total,
            "by_what": spent.by_what,
            "recent": [list(charge) for charge in spent.recent],
        }
        fd, partial = tempfile.mkstemp(dir=self._path.parent, prefix=f".{self._path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(body, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(partial, self._path)
        except BaseException:
            Path(partial).unlink(missing_ok=True)
            raise
