## Why

<!-- The problem or goal in one or two sentences. Link the issue or the decision record. -->

## What changed

<!-- The behaviour that changed, by module. New dependency: name it and say why it is worth adding. -->

## How it was verified

<!-- Exact commands and their results, e.g. "ran `uv run pytest -q`: 41 passed". Say what was not run. -->

## What needs a human

<!-- Decisions, secrets to set, things only a person can test. Or "nothing". -->

## Definition of done (docs/ENGINEERING.md §7)

- [ ] A test that fails without this change (bug fix) or covers the new behaviour (feature)
- [ ] Lint, format check, type check and tests clean locally; CI green
- [ ] Diff reviewed by the orchestrator or a teammate
- [ ] README, project guide in CLAUDE.md and decision records updated where this changes them
- [ ] Golden demo path (docs/QA.md §1) still works
- [ ] No secrets, partner data, personal data or home paths in the diff
