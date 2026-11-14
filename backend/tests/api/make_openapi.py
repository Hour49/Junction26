"""Writes docs/api/openapi-v1.json, the HTTP contract the frontend generates its types from, from
the app's own OpenAPI document (keys sorted, so the file only changes when the contract does).

    cd backend && uv run python tests/api/make_openapi.py

tests/api/test_api_openapi.py fails when the app's schema and the file differ. A change to v1 is
additive only (docs/API.md "Changing the contract").
"""

import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

OPENAPI = BACKEND.parent / "docs" / "api" / "openapi-v1.json"
COMMAND = "cd backend && uv run python tests/api/make_openapi.py"


class _NoIngest:
    """The schema needs no ingest: nothing is uploaded or read."""

    def close(self) -> None:
        pass


def schema() -> str:
    """The app's OpenAPI document as the file holds it."""
    root = Path(tempfile.mkdtemp())
    settings = Settings(projects_dir=root / "projects", credit_dataset=root, credit_photos=root)
    app = create_app(settings, _NoIngest())  # pyright: ignore[reportArgumentType]
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    OPENAPI.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI.write_text(schema(), encoding="utf-8")
    print(f"wrote {OPENAPI}")


if __name__ == "__main__":
    main()
