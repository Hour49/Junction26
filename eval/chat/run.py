"""Run the judge-like chat scripts against a running backend and record every turn.

  python3 -m chat.run --base http://127.0.0.1:8894 --mode chat --out <runs>/<name>.jsonl \
      [--only s1-doors,pdf-what] [--usd-cap 1.0]

mode chat: the agent chat (POST /chat, one chat per script, chat_id carried); the backend's
CHAT_MODEL decides rules or gemini, and each record says which. mode ask: the one-shot /ask (each
message sent as typed, no memory). The set (--scripts) and the project ids (--projects) default
to data/stoa/chat-eval/, gitignored: the truths come from partner data. Stdlib only.
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

Json = dict[str, Any]
DATA = Path(__file__).resolve().parents[2] / "data" / "stoa" / "chat-eval"
# (url, body) -> (status, reply, seconds)
Post = Callable[[str, Json], tuple[int, Json, float]]


def post(url: str, body: Json, timeout: float = 180.0) -> tuple[int, Json, float]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data, {"content-type": "application/json"}, method="POST")
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), time.monotonic() - t
    except urllib.error.HTTPError as e:
        try:
            got = json.loads(e.read())
        except ValueError:
            got = {}
        return e.code, got if isinstance(got, dict) else {}, time.monotonic() - t


def ask_view(reply: Json) -> Json:
    """What the /ask chat shows: the total (or every drawing's value), its level, the notes."""
    parts: list[Json] = reply.get("parts", [])
    refusals = [p["answer"]["refusal"] for p in parts if p["answer"].get("refusal")]
    answered = [p for p in parts if not p["answer"].get("refusal")]
    if answered:
        a = answered[0]["answer"]
        level = (a.get("level") or {}).get("level")
        reason = (a.get("check") or {}).get("reason") or (a.get("level") or {}).get("text") or ""
        unit = reply.get("total_unit") or ""
        text = f"{reply.get('total')} {unit} ({level}). {reply.get('total_note')} {reason}"
        marks = sum(len((p["answer"].get("quantity") or {}).get("marks") or []) for p in answered)
        usd = sum(p["answer"].get("cost_usd") or 0 for p in parts)
        return {"kind": "answer", "text": text.strip(), "value": reply.get("total"),
                "unit": reply.get("total_unit"), "level": reply.get("total_level"), "marks": marks,
                "options": 0, "steps": 0, "evidence": marks, "cost_usd": usd}  # fmt: skip
    text = " ".join(r.get("text", "") for r in refusals[:1]) or reply.get("total_note", "")
    options = sum(len(r.get("can_answer") or []) for r in refusals[:1])
    return {"kind": "refusal", "text": text, "value": None, "unit": None, "level": None, "marks": 0,
            "options": options, "steps": 0, "evidence": 0, "cost_usd": 0.0}  # fmt: skip


def chat_view(reply: Json) -> Json:
    """What the agent chat shows: its text and kind, and the value of the card it rests on."""
    answers: list[Json] = reply.get("answers") or []
    last: Json = answers[-1] if answers else {}
    marks = sum(len(((p.get("answer") or {}).get("quantity") or {}).get("marks") or [])
                for a in answers for p in a.get("parts", []))  # fmt: skip
    steps: list[Json] = reply.get("steps") or []
    return {"kind": reply.get("kind"), "text": reply.get("text", ""), "value": last.get("total"),
            "unit": last.get("total_unit"), "level": last.get("total_level"), "marks": marks,
            "options": len(reply.get("options") or []), "steps": len(steps),
            "evidence": len(reply.get("evidence") or []),
            "step_labels": [s.get("label") for s in steps], "view": bool(reply.get("view")),
            "cost_usd": reply.get("cost_usd") or 0.0, "model": reply.get("model"),
            "edit": bool(reply.get("edit"))}  # fmt: skip


def run(
    scripts: list[Json],
    pids: dict[str, str],
    base: str,
    mode: str,
    *,
    only: set[str] | None = None,
    usd_cap: float = 1.0,
    send: Post = post,
) -> Iterator[Json]:
    """One record per turn, in script order; stops before a turn once the spend reaches usd_cap."""
    spent = 0.0
    for script in scripts:
        if only and script["id"] not in only:
            continue
        pid = pids[script["project"]]
        chat_id: str | None = None
        for n, turn in enumerate(script["turns"], 1):
            if spent >= usd_cap:
                return
            if mode == "ask":
                status, reply, secs = send(
                    f"{base}/api/projects/{pid}/ask", {"question": turn["msg"]}
                )
                view: Json = (
                    ask_view(reply) if status == 200 else {"kind": f"http_{status}", "text": ""}
                )
            else:
                body: Json = {"message": turn["msg"]}
                if chat_id:
                    body["chat_id"] = chat_id
                if script.get("pack"):
                    body["pack"] = script["pack"]
                status, reply, secs = send(f"{base}/api/projects/{pid}/chat", body)
                view = chat_view(reply) if status == 200 else {"kind": f"http_{status}", "text": ""}
                chat_id = reply.get("chat_id", chat_id)
            usd: float = view.get("cost_usd") or 0.0
            spent += usd
            yield {"script": script["id"], "turn": n, "msg": turn["msg"], "truth": turn["truth"],
                   "mentions": turn["mentions"], "mode": mode, "status": status,
                   "latency_s": round(secs, 3), **view, "raw": reply}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--mode", choices=["ask", "chat"], default="chat")
    ap.add_argument("--scripts", type=Path, default=DATA / "scripts.json")
    ap.add_argument("--projects", type=Path, default=DATA / "ids.json")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", default="")
    ap.add_argument(
        "--usd-cap", type=float, default=1.0, help="stop when the run's spend reaches it"
    )
    args = ap.parse_args()
    scripts: list[Json] = json.loads(args.scripts.read_text())["scripts"]
    pids: dict[str, str] = json.loads(args.projects.read_text())
    only = {s for s in args.only.split(",") if s}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    with args.out.open("a") as f:
        for rec in run(scripts, pids, args.base, args.mode, only=only, usd_cap=args.usd_cap):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            usd = rec.get("cost_usd") or 0.0
            print(f"{rec['script']} t{rec['turn']} {rec['status']} {rec['latency_s']:5.1f}s "
                  f"{rec['kind']} ${usd:.4f} | {rec['text'][:150]}")  # fmt: skip
            spent += usd
    print(f"spent {spent:.4f} USD (recorded cost; a replayed call costs 0)")


if __name__ == "__main__":
    main()
