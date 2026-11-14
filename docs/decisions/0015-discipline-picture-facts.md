# 0015: A services or structural plan that is a picture is read with vision, double-checked by a second reader, and ends in the same FactSheet as an IFC model, Low until measured

- Status: proposed
- Date: 2026-11-14 21:00 (Europe/Helsinki)
- Decided by: Tudor ("pipes, heating and the other disciplines" come straight out of the classifier because they
  "can also be pictures"; "same flow as the floor plan but for the disciplines"; "do it with spec driven
  development", 2026-11-14 ~20:15). Written by agent ifc-mep for Tudor's ifc orchestrator.
- Board thread: #281

## Context

- Triage gives every 2D sheet a discipline (`Sheet.discipline`, `discipline_from_sheet`) and a kind (`mep_plan`,
  `structural_plan`). For IFC models, `facts_mep` / `facts_arch` give a `FactSheet` (`app/core/ifc_facts.py`),
  and the answer path answers from it. A services plan that arrives as a scan, photo or PDF has no reader: its
  questions (radiator counts, metres of pipe per size) are refused or fall to the floor-plan readers, which were
  trained on CubiCasa and know none of those symbols.
- There is no labelled MEP picture data. The only public symbol set found is electrical (DELP, 45 scans). A
  benchmark of VLMs on blueprint symbols reports look-alike confusions and hallucinated symbols (BlueprintSymVL).
  The dataset does have IFC service models for four buildings: pictures rendered from them come with exact truth.

## Decision

- **One branch, two lanes, one output.** A page whose triage discipline is a service or structural one (by a
  strong title word or a sheet code) goes to the discipline branch; a `mep_plan` whose title names no service is not
  routed (the sheet-kind model calls 4 of 22 labelled floor plans `mep_plan`). A vector PDF is parsed (its repeated path groups and line
  styles), with the picture lane as its check. A scan or photo is read with vision. Both write a `FactSheet` with
  the IFC fact sheets' topics (`<kind>.count`, `<kind>.length`, `<kind>.size_length`, ...), keyed by the drawing id.
  `source` names the method (`picture:vlm+template`, `vector:paths+vlm`). The answer path does not know whether a
  fact came from a model or a picture, except through `source`.
- **Read → double-check → facts**, as the floor-plan scan path:
  - a VLM reads the legend, then the plan in Carbon's tiles, one box per symbol instance;
  - a local template matcher (legend crops) or the PDF's paths reads the same labels again;
  - two readers agreeing per label is the gate, and disagreements become `check.disputed`.
- **Confidence by decision 0011, no new mechanism.** The routes `picture` and `vector` are Low (basis `unrated`) until
  the check policy names them in `route_levels`. A disputed or single-reader value is Low (basis `held`). They may be named Medium
  when the bench bar (spec AC-16) and the real-sheet check (AC-17) both pass. No High in v1.
- **Off by default**: `DISCIPLINE_PICTURES=off|vlm|vlm+template`, at most $0.15 per page (`SpendGuard`).
- **Benchmark from the models**: per-storey, per-discipline plan pictures rendered from the IFC service models
  (legend, scale bar, labels drawn in; 3 resolutions; clean, scan and photo degradation), truth = the same model's
  fact sheet, split by building into dev and test. Bogdan's 48 hard-slice sheets are the by-eye real check.
- Contract and ACs: [docs/specs/backend/discipline-pictures.md](../specs/backend/discipline-pictures.md). Owners:
  four worker slices there, with the integration by the orchestrator and Bogdan.

## Alternatives considered

- **VLM only, one reader**: cheapest to build. But it has no gate, and the published evidence is that VLMs
  hallucinate drawing symbols. Every answer would stay Low with nothing to point at.
- **Train an MEP symbol detector**: no labelled data. Rendered pictures could train one, but a detector trained on
  our own renderer's symbols would score well on our own bench and say little about real sheets. It can come after
  the bench shows where the VLM fails.
- **Send discipline sheets to the floor-plan readers**: they know 14 architectural classes (`ElementClass`) and no
  MEP symbol, so they would give confident wrong zeros.
- **A separate answer path for pictures**: two paths for the same question families. The shared `FactSheet` keeps
  one answer path, and the route keeps the confidence honest.

## Consequences

- `Fact` gains an additive `spots` field (page boxes per counted thing) for the viewer and the double-check: an
  ifc-arch change through the orchestrator. IFC facts leave it empty.
- The answer path maps `source` → route (`picture`, `vector`, `ifc`) for `level_of`: an ifc-ask change.
- New work: four worker slices (core, readers, bench renderer, bench scorer), with tests first from the ACs.
- The bench is synthetic. Passing it shows the readers work on clean conventions, not on any office's real symbol
  style. That is why the real-sheet check gates Medium too.
- Revisit when labelled real MEP sheets exist (then High can be measured), when a trained detector beats the
  template reader on dev, or when the cost per page goes over budget on real sheets.
