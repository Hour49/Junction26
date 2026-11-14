"""A live smoke test of the agent chat on Gemini (decision 0013), by hand, never in CI: three turns
on a project, each printed with its kind, text, steps and cost. Every model call is charged to the
Gemini spend guard (GEMINI_BUDGET_USD / _PER_HOUR from .env bound it). Run from backend/ with
CHAT_MODEL=gemini and GEMINI_API_KEY in .env or the environment:

    uv run python scripts/agent_smoke.py --project <project id>     # a project in PROJECTS_DIR
    uv run python scripts/agent_smoke.py --pdf <path to a plan PDF>  # uploaded as a new project
    uv run python scripts/agent_smoke.py --pdf <path> "first message" "second" "third"
"""

import argparse
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for `app`

from app.composition import build_ingest, spend_guard
from app.main import create_app
from app.settings import Settings

TURNS = (
    "How big is the bathroom?",
    "Remove the wall between the bathroom and the bedroom to make the bathroom larger",
    "Is that wall load-bearing?",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--project", help="a project id (12 hex) in PROJECTS_DIR")
    where.add_argument("--pdf", type=Path, help="a plan PDF to upload as a new project")
    parser.add_argument("messages", nargs="*", default=list(TURNS), help="the turns to send")
    args = parser.parse_args()
    settings = Settings()
    if settings.chat_model != "gemini" or not settings.gemini_api_key.get_secret_value():
        print("refused: set CHAT_MODEL=gemini and GEMINI_API_KEY (this script calls Gemini)")
        return 2
    client = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = args.project
    if args.pdf is not None:
        response = client.post(
            "/api/projects", params={"name": args.pdf.name}, content=args.pdf.read_bytes()
        )
        response.raise_for_status()
        project = response.json()["id"]
    print(f"project {project}, model {settings.agent_model}")
    chat_id = None
    for message in args.messages:
        body = {"message": message, **({"chat_id": chat_id} if chat_id else {})}
        response = client.post(f"/api/projects/{project}/chat", json=body)
        if response.status_code != 200:
            print(f"> {message}\n  HTTP {response.status_code}: {response.json().get('detail')}")
            return 1
        turn = response.json()
        chat_id = turn["chat_id"]
        print(f"> {message}\n  {turn['kind']}: {turn['text']}")
        for option in turn["options"] or []:
            print(f"  option: {option['label']} -> {option['message']}")
        for step in turn["steps"]:
            print(f"  step {step['n']} {step['status']} {step['ms']} ms: {step['label']}")
        edit = turn["edit"]
        if edit:
            for room in edit["rooms"]:
                print(
                    f"  room {room['label']}: {room['area_before_m2']} -> {room['area_after_m2']}"
                )
        print(
            f"  ${turn['cost_usd']:.4f}, {turn['latency_s']:.1f} s, {len(turn['evidence'])} sources"
        )
    print(f"spent this run: ${spend_guard(settings).spent_by().get('agent chat', 0.0):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
