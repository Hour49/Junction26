#!/usr/bin/env python3
"""End-to-end smoke test of a running Stoa env: the real flows over HTTP, a pass/fail table and
an exit code.

    python3 tools/smoke.py <base-url> [--zip <zip> | --no-upload] [--paid] [--timeout S]
                           [--header 'Name: value' ...]

<base-url> is the one origin the browser uses (tools/qa-env.sh --frontend's port, or the deploy):
/, /health and /api on it. Steps, in order:
  health    GET /health is {"status": "ok"}
  info      GET /api/info: readers and limits; the commit and the Gemini status (with
            budget_exhausted) when the backend gives them, noted as absent otherwise
  frontend  GET / serves the app's HTML
  sample    POST /api/projects/sample, polled to done; then the project checks below
  upload    POST /api/projects?name=<zip> with --zip (default data/demo/demo-project.zip),
            polled to done within --timeout; then the project checks below
Per project: every file in a final state; none failed unexpectedly (a stage failure or "not
ingested"; a file set aside as not a plan or as a format that is not read is fine); GET
/api/drawings/{id} for each drawing; fixed count questions through POST /api/ask (what the chat
sends) on the first drawing of each route, each with a value, its `confidence` and `check`
fields and marks; one question that must be refused; POST /api/projects/{id}/ask; issues and
checks (the first rule pack of /api/info). Without --paid every cost the API reports (project,
files, trace stages, answers) must be $0: no Gemini call was paid for. Standard library only.
Exit 0: every check passed; 1: a check failed; 2: bad arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_ZIP = ROOT / "data/demo/demo-project.zip"
FINISHED = {"ready", "flagged", "text_only", "set_aside"}
COUNTS = ("How many doors are there?", "How many windows are there?")
REFUSED = "What colour is the roof?"
POLL_S = 2.0


@dataclass(frozen=True)
class Check:
    step: str
    name: str
    ok: bool
    detail: str = ""


class Api:
    def __init__(self, base: str, headers: dict[str, str], timeout: float = 60.0) -> None:
        self.base = base.rstrip("/")
        self.headers = headers
        self.timeout = timeout

    def call(
        self, method: str, path: str, body: bytes | None = None, kind: str = "application/json"
    ) -> tuple[int, bytes, str]:
        """(HTTP status, body, content type); no connection: status 0, the error as the body."""
        headers = dict(self.headers)
        if body is not None:
            headers["Content-Type"] = kind
        request = urllib.request.Request(
            self.base + path, data=body, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as reply:
                return reply.status, reply.read(), reply.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            return 0, str(error).encode(), ""

    def json(self, method: str, path: str, payload: object = None) -> tuple[int, object]:
        body = None if payload is None else json.dumps(payload).encode()
        status, data, _ = self.call(method, path, body)
        try:
            return status, json.loads(data)
        except ValueError:
            return status, data.decode(errors="replace")[:200]


# --- pure checks (tests: tools/test_smoke.py) ------------------------------------------------


def health_check(status: int, body: object) -> Check:
    ok = status == 200 and isinstance(body, dict) and body.get("status") == "ok"
    return Check("health", "GET /health", ok, "" if ok else f"{status} {body}")


def info_checks(status: int, info: object) -> list[Check]:
    """/api/info: readers and limits must be there. The commit (APP_COMMIT; null when the backend
    was started without it) and the Gemini status (`gemini`: "ok", or "budget_exhausted", which
    fails; left out when no budget is set) are reported."""
    if status != 200 or not isinstance(info, dict):
        return [Check("info", "GET /api/info", False, f"{status} {info}")]
    readers = info.get("readers")
    out = [
        Check(
            "info",
            "GET /api/info",
            isinstance(readers, dict) and bool(readers) and "limits" in info,
            f"no_keys {info.get('no_keys')}; readers "
            + ", ".join(f"{k}={v}" for k, v in (readers or {}).items()),
        )
    ]
    out.append(Check("info", "commit", True, commit_of(info)))
    gemini = info.get("gemini")
    budget = _find(info, "budget_exhausted")
    exhausted = gemini == "budget_exhausted" or budget is True
    if gemini is None:
        detail = "no budget set (no `gemini` in /api/info)"
    else:
        detail = json.dumps(gemini, sort_keys=True)
    out.append(Check("info", "gemini status", not exhausted, detail))
    return out


def commit_of(info: object) -> str:
    """The commit /api/info names, or why there is none."""
    if not isinstance(info, dict) or "commit" not in info:
        return "absent (not in /api/info)"
    return str(info["commit"]) if info["commit"] else "null (the backend has no APP_COMMIT)"


def _find(data: object, key: str) -> object:
    """The first value under `key` anywhere in a JSON value; None when absent."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        values = list(data.values())
    elif isinstance(data, list):
        values = data
    else:
        return None
    for value in values:
        found = _find(value, key)
        if found is not None:
            return found
    return None


def frontend_check(status: int, body: bytes, kind: str) -> Check:
    text = body[:4000].decode(errors="replace").lower()
    ok = status == 200 and "html" in kind and "<html" in text and "<script" in text
    return Check("frontend", "GET /", ok, "" if ok else f"{status} {kind} {text[:80]!r}")


def unexpected_failure(file: dict, stages: list[dict]) -> str | None:
    """Why a file failed unexpectedly, or None. A set-aside because the file is not a plan or its
    format is not read is expected; a stage failure or "not ingested" (a crash, a restart) is
    not."""
    failed = [s for s in stages if s.get("failure")]
    if failed:
        return f"{failed[0].get('stage')}: {failed[0]['failure']}"
    if str(file.get("reason", "")).startswith("not ingested"):
        return str(file["reason"])
    return None


def file_checks(step: str, project: dict, traces: list[dict]) -> list[Check]:
    files = project.get("files", [])
    stages = {
        t["file"]["id"]: t.get("stages", []) for t in traces if isinstance(t, dict) and "file" in t
    }
    states: dict[str, int] = {}
    for file in files:
        states[file.get("state")] = states.get(file.get("state"), 0) + 1
    unfinished = [
        f"{f['id']} {f['path']}: {f.get('state')}" for f in files if f.get("state") not in FINISHED
    ]
    failed = []
    for file in files:
        why = unexpected_failure(file, stages.get(file["id"], []))
        if why:
            failed.append(f"{file['id']} {file['path']}: {why}")
    summary = ", ".join(f"{k} {v}" for k, v in sorted(states.items()))
    return [
        Check(
            step,
            "project done",
            project.get("state") == "done",
            str(project.get("state"))
            + (f"; error {project['error']}" if project.get("error") else ""),
        ),
        Check(
            step,
            "every file final",
            bool(files) and not unfinished,
            f"{len(files)} files: {summary}" + (f"; not final: {unfinished}" if unfinished else ""),
        ),
        Check(step, "no unexpected failure", not failed, "; ".join(failed) or "none"),
        Check(
            step,
            "drawings",
            bool(project.get("drawings")),
            f"{len(project.get('drawings', []))} drawings",
        ),
    ]


def costs(project: dict, traces: list[dict]) -> list[tuple[str, float]]:
    """Every non-zero cost the project's status and traces report, as (where, USD)."""
    found = []
    if project.get("cost_usd"):
        found.append(("project", float(project["cost_usd"])))
    for file in project.get("files", []):
        if file.get("cost_usd"):
            found.append((f"file {file['id']} {file['path']}", float(file["cost_usd"])))
    for trace in traces:
        for stage in trace.get("stages", []):
            if stage.get("cost_usd"):
                found.append(
                    (f"{trace['file']['id']} stage {stage.get('stage')}", float(stage["cost_usd"]))
                )
    return found


def cost_check(step: str, spent: list[tuple[str, float]], paid: bool) -> Check:
    total = sum(usd for _, usd in spent)
    detail = f"${total:.4f}" + (
        f" ({'; '.join(f'{w} ${u:.4f}' for w, u in spent[:5])})" if spent else ""
    )
    return Check(
        step, "no paid model call" if not paid else "cost (--paid)", paid or not spent, detail
    )


def answer_check(step: str, file: str, question: str, status: int, answer: object) -> Check:
    """A count question through POST /api/ask: a value, the confidence and check fields, and for a
    count above 0 its proof: marks on the page, or the model objects it counted (an IFC model has
    no page to mark)."""
    name = f"ask {question!r} on {file}"
    if status != 200 or not isinstance(answer, dict):
        return Check(step, name, False, f"{status} {answer}")
    missing = [
        k
        for k in ("answer", "confidence", "check", "marks", "refusal", "cost_usd")
        if k not in answer
    ]
    if missing:
        return Check(step, name, False, f"fields missing: {missing}")
    value, refusal, marks = answer["answer"], answer["refusal"], answer["marks"]
    objects = (answer.get("proof") or {}).get("objects") or []
    sure = (answer.get("line") or {}).get("sure")
    detail = (
        f"value {value} {answer.get('unit') or ''}, marks {len(marks)}, objects {len(objects)}, "
        f"confidence {'set' if answer['confidence'] else 'none'}, "
        f"check {'set' if answer['check'] else 'none'}, "
        f"sure {sure}"
    )
    if refusal is not None:
        return Check(
            step, name, False, f"refused: {refusal.get('code')} {refusal.get('text', '')[:80]}"
        )
    ok = (
        value is not None
        and isinstance(marks, list)
        and (not isinstance(value, int | float) or value == 0 or bool(marks) or bool(objects))
    )
    return Check(step, name, ok, detail)


def refusal_check(step: str, file: str, status: int, answer: object) -> Check:
    name = f"ask {REFUSED!r} on {file}"
    ok = (
        status == 200
        and isinstance(answer, dict)
        and answer.get("answer") is None
        and answer.get("refusal")
    )
    detail = f"{status} " + (
        str((answer.get("refusal") or {}).get("code")) if isinstance(answer, dict) else str(answer)
    )
    return Check(step, name, bool(ok), detail)


def project_ask_check(step: str, status: int, body: object) -> Check:
    ok = status == 200 and isinstance(body, dict) and bool(body.get("parts"))
    detail = (
        f"{len(body.get('parts', []))} parts, total {body.get('total')}"
        if isinstance(body, dict)
        else str(body)
    )
    return Check(step, f"POST /api/projects/<id>/ask {COUNTS[0]!r}", ok, f"{status} {detail}")


def listed_check(step: str, name: str, status: int, body: object, key: str) -> Check:
    ok = status == 200 and isinstance(body, dict) and isinstance(body.get(key), list)
    detail = f"{len(body[key])} {key}" if ok else f"{status} {str(body)[:120]}"
    return Check(step, name, ok, detail)


def first_per_route(drawings: list[dict]) -> list[dict]:
    """The first drawing of each route (raster, vector, bim...), in the project's order."""
    seen, out = set(), []
    for drawing in drawings:
        if drawing.get("route") not in seen:
            seen.add(drawing.get("route"))
            out.append(drawing)
    return out


def table(checks: list[Check]) -> str:
    rows = ["| step | check | result | detail |", "| --- | --- | --- | --- |"]
    for c in checks:
        rows.append(
            f"| {c.step} | {c.name} | {'pass' if c.ok else 'FAIL'} | {c.detail.replace('|', '/')} |"
        )
    failed = sum(not c.ok for c in checks)
    rows.append("")
    rows.append(f"{len(checks) - failed} passed, {failed} failed")
    return "\n".join(rows)


# --- flows -----------------------------------------------------------------------------------


def wait_done(api: Api, project_id: str, timeout: float) -> tuple[dict | None, float]:
    started = time.monotonic()
    while True:
        status, project = api.json("GET", f"/api/projects/{project_id}")
        if (
            status == 200
            and isinstance(project, dict)
            and project.get("state") in ("done", "failed")
        ):
            return project, time.monotonic() - started
        if time.monotonic() - started > timeout:
            return (project if isinstance(project, dict) else None), time.monotonic() - started
        time.sleep(POLL_S)


def project_flow(
    api: Api, step: str, started: tuple[int, object], timeout: float, paid: bool, pack: str | None
) -> list[Check]:
    status, body = started
    if status != 202 or not isinstance(body, dict) or "id" not in body:
        return [Check(step, "start", False, f"{status} {body}")]
    pid = body["id"]
    project, seconds = wait_done(api, pid, timeout)
    out = [
        Check(
            step,
            "start + poll",
            project is not None and project.get("state") in ("done", "failed"),
            f"project {pid}, {project.get('state') if project else 'no reply'} "
            f"after {seconds:.0f} s"
            f" (timeout {timeout:.0f} s)",
        )
    ]
    if not project or project.get("state") not in ("done", "failed"):
        return out
    tstatus, trace = api.json("GET", f"/api/projects/{pid}/trace")
    traces = trace.get("files", []) if tstatus == 200 and isinstance(trace, dict) else []
    out.append(
        Check(step, "GET trace", tstatus == 200 and bool(traces), f"{tstatus}, {len(traces)} files")
    )
    out += file_checks(step, project, traces)
    spent = costs(project, traces)
    drawings = project.get("drawings", [])
    bad = []
    for drawing in drawings:
        dstatus, _ = api.json("GET", f"/api/drawings/{drawing['drawing_id']}")
        if dstatus != 200:
            bad.append(f"{drawing['file']}: {dstatus}")
    out.append(
        Check(
            step,
            "GET /api/drawings/<id> each",
            bool(drawings) and not bad,
            f"{len(drawings) - len(bad)}/{len(drawings)} read" + (f"; {bad}" if bad else ""),
        )
    )
    for drawing in first_per_route(drawings):
        for question in COUNTS:
            astatus, answer = api.json(
                "POST",
                "/api/ask",
                {"drawing_id": drawing["drawing_id"], "question": question, "project_id": pid},
            )
            out.append(
                answer_check(
                    step, f"{drawing['file']} ({drawing.get('route')})", question, astatus, answer
                )
            )
            if isinstance(answer, dict) and answer.get("cost_usd"):
                spent.append((f"answer on {drawing['file']}", float(answer["cost_usd"])))
    if drawings:
        rstatus, refused = api.json(
            "POST",
            "/api/ask",
            {"drawing_id": drawings[0]["drawing_id"], "question": REFUSED, "project_id": pid},
        )
        out.append(refusal_check(step, drawings[0]["file"], rstatus, refused))
        if isinstance(refused, dict) and refused.get("cost_usd"):
            spent.append(("refusal answer", float(refused["cost_usd"])))
        out.append(
            project_ask_check(
                step, *api.json("POST", f"/api/projects/{pid}/ask", {"question": COUNTS[0]})
            )
        )
    out.append(
        listed_check(step, "GET issues", *api.json("GET", f"/api/projects/{pid}/issues"), "issues")
    )
    if pack is None:
        out.append(Check(step, "GET checks", False, "no rule pack in /api/info"))
    else:
        q = urllib.parse.quote(pack)
        out.append(
            listed_check(
                step,
                f"GET project checks pack={pack}",
                *api.json("GET", f"/api/projects/{pid}/checks?pack={q}"),
                "drawings",
            )
        )
        if drawings:
            did = drawings[0]["drawing_id"]
            out.append(
                listed_check(
                    step,
                    f"GET drawing checks pack={pack}",
                    *api.json("GET", f"/api/drawings/{did}/checks?pack={q}&project={pid}"),
                    "rules",
                )
            )
    out.append(cost_check(step, spent, paid))
    return out


def run(
    base: str, zip_path: Path | None, paid: bool, timeout: float, headers: dict[str, str]
) -> list[Check]:
    api = Api(base, headers)
    checks = [health_check(*api.json("GET", "/health"))]
    istatus, info = api.json("GET", "/api/info")
    checks += info_checks(istatus, info)
    checks.append(frontend_check(*api.call("GET", "/")))
    packs = info.get("rule_packs", []) if isinstance(info, dict) else []
    pack = packs[0]["id"] if packs and isinstance(packs[0], dict) and "id" in packs[0] else None
    checks += project_flow(
        api, "sample", api.json("POST", "/api/projects/sample"), timeout, paid, pack
    )
    if zip_path is not None:
        name = urllib.parse.quote(zip_path.name)
        status, data, _ = api.call(
            "POST", f"/api/projects?name={name}", zip_path.read_bytes(), "application/zip"
        )
        try:
            started: tuple[int, object] = (status, json.loads(data))
        except ValueError:
            started = (status, data.decode(errors="replace")[:200])
        checks += project_flow(api, "upload", started, timeout, paid, pack)
    return checks


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base_url")
    parser.add_argument(
        "--zip", type=Path, default=DEMO_ZIP, help=f"the upload (default {DEMO_ZIP.name})"
    )
    parser.add_argument("--no-upload", action="store_true", help="the sample project only")
    parser.add_argument("--paid", action="store_true", help="allow paid model calls (Gemini)")
    parser.add_argument(
        "--timeout", type=float, default=900.0, help="seconds per project to reach done"
    )
    parser.add_argument(
        "--header", action="append", default=[], help="'Name: value', sent on every request"
    )
    args = parser.parse_args(argv)
    if not args.base_url.startswith(("http://", "https://")):
        parser.error("base-url must start with http:// or https://")
    for header in args.header:
        if ":" not in header:
            parser.error(f"--header must be 'Name: value': {header!r}")
    if not args.no_upload and not args.zip.is_file():
        parser.error(f"no zip at {args.zip}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(sys.argv[1:] if argv is None else argv)
    headers = {k.strip(): v.strip() for k, v in (h.split(":", 1) for h in args.header)}
    started = time.monotonic()
    checks = run(
        args.base_url, None if args.no_upload else args.zip, args.paid, args.timeout, headers
    )
    print(table(checks))
    commit = next((c.detail for c in checks if c.name == "commit"), "unknown (no /api/info)")
    print(
        f"{args.base_url} · commit {commit} · "
        f"{'paid calls allowed' if args.paid else 'no paid calls'} · "
        f"{time.monotonic() - started:.0f} s"
    )
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
