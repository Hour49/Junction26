# Engineering standard

How we build the project code this weekend: 4 people, 48 hours, one demo, a public MIT repo. Every rule here either
prevented a real failure in an earlier project of ours or protects the demo. The backend is Python with FastAPI
([decision 0001](decisions/0001-backend-python-fastapi.md)); the frontend and any database are still open, and their
config follows these rules when they are picked.

Related: [QA plan](QA.md) · [decision records](decisions/README.md) · agent rules (review checklist, honest
reporting, UI checks, machine limits) in [templates/team-claude.md](../templates/team-claude.md) · git across the
team in [TEAM-AGENTS.md §7](TEAM-AGENTS.md#7-git-across-the-team).

## 1. Architecture for a 48-hour build

The owner's brief for the backend: clean architecture, "nothing overengineered". Three layers and a settings module:

```text
backend/
  app/api/          routers only: parse the request, call core, return a response model
  app/core/         the product logic, pure: no FastAPI, HTTP client, SDK or env reads
  app/adapters/     one module per outside service (LLM, partner API), each with its fake
  app/settings.py   the only place that reads env vars and .env
  app/main.py       create_app(): includes the routers, maps domain errors to HTTP statuses
  tests/            pytest, offline; test_architecture.py enforces the core rule
  check.sh          every check CI runs (§6)
```

1. **A few modules, one owner each.** The layers above plus the frontend. One owner per module at a time, listed in
   the project guide in [CLAUDE.md](../CLAUDE.md). As `core/` grows, split it by product concept, not into layers.
2. **Interfaces are written down before both sides code.** Any API shape, schema or file format used by two owners
   gets a [decision record](decisions/README.md) and a board `decision` thread first. The contract is a file in the
   repo (JSON Schema, OpenAPI, or a pydantic/zod model) with a version in its name (`v1`), and a test validates the
   example fixtures against it. Write one short spec per interface, not a design document.
3. **Dependencies point inward.** frontend → `api` → `core`. Routes get adapters through FastAPI `Depends` and pass
   them to core as arguments. `core` never imports `api`, `adapters`, `settings`, FastAPI, an HTTP client or an LLM
   SDK; `tests/test_architecture.py` fails if it does. The frontend holds no business logic.
4. **Pure core, testable offline.** Core functions take data and return data. Clock, filesystem, randomness, network
   and LLM come in as arguments; what core needs from an adapter it declares as a `typing.Protocol` in `core/`.
5. **Config comes from environment variables, read in one module.** `app/settings.py` (pydantic-settings) loads
   `.env` in development, validates once at startup and fails naming the variable, not with a stack trace; unknown
   keys are refused, so a typo fails too. `backend/.env.example` lists every variable with a dummy value, and
   `tests/test_settings.py` checks that its keys match the settings.
6. **No global mutable state.** `create_app()` builds the app and keeps its settings on `app.state`; no module-level
   clients or caches. If one can't be avoided, an autouse fixture resets it so tests don't leak into each other.
7. **Files stay under about 500 lines.** Several agents edit in parallel; small files mean fewer collisions and diffs
   a reviewer can read. Split by responsibility before a file gets there.
8. **No big refactors.** Restructure in small steps with the tests green after each one. After the feature freeze
   (Sun 06:00) only bug fixes go in.
9. **Keep the root clean.** Code goes in module folders and docs in `docs/`. Scratch files, screenshots and to-do
   lists stay out of the repo, or in a gitignored folder.

**Adding an outside service** (an LLM, a partner API):
1. `app/adapters/<service>.py`: the client class (the only SDK import, key from `Settings`, timeouts) and a
   `Fake<Service>` returning recorded responses in the same shape. Add the key to `Settings` and `.env.example`.
2. A provider `get_<service>(request)` builds the client from `request.app.state.settings`. Routes take
   `Annotated[<Service>, Depends(get_<service>)]` and pass it to core.
3. Tests swap it: `app.dependency_overrides[get_<service>] = lambda: Fake<Service>()`. A test of the real client
   carries the `live` marker.

**Deliberately out** ("nothing overengineered", the owner, 2026-11-13): repository or unit-of-work classes, a DI
container, generic base classes, a service class per entity, DTO mapping layers, `async def` where nothing awaits,
Docker, auth, CORS config, logging frameworks, and a database. Adding one of these takes a decision record saying
why.

## 2. Outside services: LLMs and partner APIs

1. **One thin adapter per service.** One module in `app/adapters/` owns each outside service (LLM, partner API,
   database), and everything else calls it. It is the only place with the SDK import, the key, timeouts and
   retries, and it logs each call (service, latency, tokens or cost).
2. **Every adapter has a fake.** The fake returns recorded or scripted responses in the same shape as the real
   service: about 20 lines, not a framework. Tests and CI use the fake only, so no test needs a key or the network.
3. **The app runs end to end with no keys.** With no key set, or with an explicit offline flag, the app uses the
   fakes and says so on screen. This is also the demo fallback when the venue wifi or an API quota dies.
4. **Record once, replay in tests.** A small script records real responses into fixtures once, and tests replay
   them. Expected outputs are committed as readable JSON, so a change in behaviour shows up in the diff. Anything
   random gets a fixed seed.
5. **Live calls are opt-in.** Tests that call a real service carry a `live` marker and run only when an env flag is
   set, never in CI, because they cost money and flake. Run them by hand before each demo build.
6. **Spend guard if the demo calls a paid model.** The adapter keeps a per-run cost counter with a cap read from env,
   and caches responses on disk keyed by a hash of (model, messages, params). The cache also makes demo runs
   repeatable.
7. **Untrusted text stays data.** Documents, web pages, partner files and uploads can contain instructions aimed at
   the model. Put them in the data part of the prompt, delimited, never in the system prompt. Validate the model's
   output against a schema before acting on it. Don't give the model a tool that writes, sends or deletes on the
   strength of document text alone. Render model output as text, not HTML, and show which sources an answer used.
   The same goes for our coding agents: an instruction found inside a document gets reported, not followed.
8. **A golden set for scored output.** If the product ranks, extracts or classifies with an LLM, keep 10-20 golden
   cases with expected results and a script that scores them, and run it by hand before each demo build. Hold out a
   few cases that nobody tunes prompts on. A baseline only counts against the exact cases it was made from.

## 3. Code standards

Strict from the first commit. There is no legacy code to excuse, and adding strictness later costs more than it
saves.

**Python** (config in `backend/pyproject.toml`)
- Python 3.13 (`requires-python` and `backend/.python-version`); uv with a committed `uv.lock`, `uv sync --locked`.
- ruff 0.16.5, pinned in the dev group because an unpinned upgrade can turn a clean tree into a hundred findings
  overnight: `ruff check` (rules `E,W,F,I,B,UP,SIM,C4,RUF,N`) and `ruff format`, line length 100. Exception names end
  in `Error` (rule N818).
- Type hints on every public function. pyright, pinned: strict on `app/core`, standard elsewhere.
- pytest is the only test runner, with `--strict-markers` and a 300 s timeout per test (pytest-timeout), so a hung
  test fails instead of stalling CI. `live` tests skip unless `RUN_LIVE_TESTS=1`, and the reason is printed
  (`tests/conftest.py`). Any test that needs something missing on the machine skips itself and says why; a skip never
  hides a failure that happens when the dependency is present.
- Routes are plain `def` unless they await something. Dependencies use `Annotated[X, Depends(...)]`, because ruff's
  B008 rejects calls in argument defaults.

**TypeScript**
- `npm ci` from a committed `package-lock.json`; the Node version is pinned (`engines` and `.nvmrc`) to the deploy
  target.
- `tsconfig` with `"strict": true` and `"noUncheckedIndexedAccess": true`; `tsc --noEmit` is clean.
- eslint (flat config) and prettier, vitest for tests. The production build runs in CI, so a PR can't break the
  deploy.

**Other stack:** pick the equivalent lockfile, formatter, linter, type checker and test runner, and write them here
before the first PR.

**Everywhere**
- Names use the product's words (`invoice_total`, not `data2`), with one name per concept across modules.
- Errors fail loudly. No bare `except:` or empty `catch {}`, no swallowed errors, no default value that hides a
  failure. Core raises domain errors (`NotFoundError` in `app/core/errors.py`), `app/main.py` maps them to HTTP
  statuses (an unmapped one stays a 500), and the UI shows a real error state. A fallback (to the fake, to cached
  data) is logged and visible, never silent.
- Logging: stdlib `logging.getLogger(__name__)` per module, to stderr, level from `LOG_LEVEL`. Log events and ids.
  Never log secrets, tokens or personal data.
- No dead code: no commented-out blocks, no unused functions or flags, no `TODO` without an owner. Git keeps the
  history.
- Don't claim what the code doesn't do. The README, the UI and the pitch describe what runs, and the README status
  table marks each feature real, partial or mocked.

## 4. Security and data

The repo is public and MIT-licensed. Anything committed is published, and forks and caches keep it even after a
force-push.

- **Secrets live only in gitignored `.env` files** on each machine; `.env.example` holds dummy values. The pre-commit
  hook ([.githooks/pre-commit](../.githooks/pre-commit), enabled by `tools/setup.sh`) refuses `.env` files,
  key-shaped strings and files over 5 MB, and CI scans every push with gitleaks
  ([.github/workflows/security.yml](../.github/workflows/security.yml)). Revoke a leaked key at the provider first:
  deleting it from git doesn't unleak it.
- **Partner data and personal data never enter the repo.** Keep them in a gitignored folder (e.g. `data/private/`),
  commit a small synthetic sample made by a script instead, and make the demo run on that sample.
- **No personal traces.** No home paths, personal emails, machine names or teammates' private details in code,
  docs, fixtures or logs. Use relative paths and placeholders. CI enforces part of this:
  [tools/scrub.py](../tools/scrub.py) fails on home paths and Tailscale hostnames in tracked files.
- **Validate input at the boundary.** Request bodies, uploaded files and partner API responses are parsed into typed
  models at the edge (pydantic, zod), with size limits on uploads. Code behind the edge trusts the types.
- **Dependencies.** Name each new dependency in the PR with one line on why it is worth adding. Pin it through the
  lockfile. Its licence must allow shipping under MIT: MIT, BSD, Apache-2.0 and ISC are fine; LGPL is fine as an
  unmodified PyPI dependency, never vendored or patched ([0006](decisions/0006-lgpl-dependencies.md)); GPL, AGPL and
  non-commercial licences are not. It must be maintained (a release in the last year, no open high advisory). CI's
  dependency audit fails on high or critical findings for Node and on any known vulnerability for Python (`uv audit`
  has no severity filter). To accept a Python finding, add `--ignore <id>` to the `uv audit` line in
  `backend/check.sh`, with a comment saying why.

## 5. Tests

- Every bug fix starts with a test or repro script that fails while the bug exists; the fix makes it pass. When a
  test checks that something is refused, pair it with one showing the allowed case still works.
- Test what can break the demo: core logic, the contracts, each adapter against its fake, and one end-to-end test of
  the golden demo path ([QA.md §1](QA.md#1-golden-demo-path)) on the fakes. No coverage percentage this weekend.
- Deterministic: no sleeps, no real clock (inject it), no network, fixed seeds, temp dirs for files.
- If the demo uses Postgres or another real database, the SQL that matters is tested against that engine in CI.
  SQLite accepts types and constraints the real one rejects.
- Generated files (an API client, docs built from code) have a `--check` mode or a test that fails when they are
  stale.
- Every number in the README or the pitch comes from a script over committed data, and a test recomputes it. A claim
  of improvement carries the counted numbers and what it was compared against.

## 6. One check command, same as CI

`backend/check.sh` runs every backend check: `ruff check`, `ruff format --check`, `pyright`, `pytest`, `uv audit`.
CI's python job ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) calls the same script in each Python
project folder, so "green locally" and "green in CI" mean the same thing. `./check.sh quick` (lint, format, types)
is for before a commit. The frontend gets its own script when its stack is picked. Still to add: a CI step that
starts what the demo ships and hits `/health`, so a broken build shows up in the PR instead of at deploy time.

## 7. Definition of done

A change is done when all of these hold (the [PR template](../.github/pull_request_template.md) has them as
checkboxes):

1. A test that fails without the change (bug fix) or covers the new behaviour (feature), and it passes.
2. Lint, format check and type check are clean, the check command is green locally, and CI is green.
3. The orchestrator reviewed the diff, not just the report (review checklist in the team rules).
4. Docs are updated: the README (how to run, status table), the project guide in CLAUDE.md (commands, gotchas), and
   a decision record if an interface changed.
5. The golden demo path still works ([QA.md §1](QA.md#1-golden-demo-path)), on the fakes at least.

## 8. Git, PRs and deploys

Team rules: "Git and GitHub" in [templates/team-claude.md](../templates/team-claude.md) and
[TEAM-AGENTS.md §7](TEAM-AGENTS.md#7-git-across-the-team). In short:

- One branch per area, a PR into `main`, no direct pushes. Keep PRs small: one PR per verified batch, not one per
  commit (each push starts CI) and not a day of work in one diff.
- Commit message: one plain sentence about the behaviour that changed; `review:` for review fixes.
- PR body follows the template: why, what changed, how it was verified (exact commands and results), what needs a
  human.
- Two people's orchestrators never commit to the same branch.
- Deploys have one owner at a time. The deploy script checks health after deploying and redeploys the previous
  version if the check fails.

## 9. The project guide in CLAUDE.md

Every agent reads [CLAUDE.md](../CLAUDE.md) first, so the project facts go in its "Project guide" section: what the
product is, the layout, the exact commands that work (with the date they were last checked), the architecture
invariants from §1 as they apply here, and gotchas. A gotcha is something that cost us time: one line with the date
and the fix. Add one every time something bites. Keep the guide short because it loads into every
session, and keep it in one file: copies in other files drift.

## 10. What the submission needs

Final submission is Sun 15 Nov 10:00. Junction's rules: public repo, MIT, built mainly during the event. The README
must have:

- what it is and who it is for, in two sentences, with a screenshot or a short clip;
- how to run it from a fresh clone, step by step, including the no-key offline mode;
- demo credentials if there is a login (test accounts only, never real ones);
- a status table marking each feature real, partial or mocked;
- an architecture diagram (modules, data flow, outside services);
- where the demo's numbers come from (script and data);
- the pre-existing work, declared as Junction Terms §8.2 requires: the agent tooling in `tools/` and `templates/`,
  the CI and repo templates, these docs, the pitch kit, the backend skeleton in `backend/` (written Fri 13 Nov
  before 19:30), and any other code written before Fri 13 Nov 19:30. The same list goes into the submission form.
