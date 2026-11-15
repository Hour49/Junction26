# Discipline pictures: facts from a services or structural plan that is a picture (spec)

Status: proposed, 2026-11-14 21:00, by ifc-mep (brief disc-spec.md). Decision:
[0015](../../decisions/0015-discipline-picture-facts.md), board #281. Nothing here is built yet: the
implementation workers write tests from the ACs below first, then the code.

## Purpose

Tudor (2026-11-14 ~20:15): the classifier sends every file one of three ways: a floor plan, a discipline sheet
(piping, heating, ventilation, electrical, structural), or everything else. The discipline branch has the same shape
as the floor-plan branch: **model or scan?** Models and vector PDFs are parsed exactly. Pictures (scans, photos)
are **read with vision**, then **double-checked**. Both kinds end in the **same `FactSheet`** (`app/core/ifc_facts.py`)
and go to the **answer**, which is Low until measured.

This spec is the picture lane: a page of a services or structural plan → a `FactSheet` with the same topics the IFC
fact sheets use, with a mark on the page for every counted thing, so "how many radiators on floor 2" or "metres of
DN20 heating pipe" is answered the same way from a scan as from a model.

## Scope

In:
- Counts of the symbols a legend names, as the IFC kinds (`space_heater`, `light_fixture`, `outlet`,
  `air_terminal`, `sanitary_terminal`, `valve`, `fire_suppression_terminal`, `alarm`, `switching_device`,
  `column`, `pile`, `footing`, ...), per legend label, per sheet.
- Run lengths of line-drawn systems (pipes, ducts, cable trays), per system and per printed size, **only when the
  sheet has a scale**.
- One page at a time, page 1 of the file (as every raster reader today).

Non-goals (v1):
- Schedules on the sheet (already `TABLES=pdf`), title-block metadata beyond the storey, rebar and reinforcement
  details, sections and isometrics (`sheet_kind` detail/section/axonometric), riser diagrams, connectivity tracing
  between symbols, sizes not printed on the sheet, cross-sheet totals (the answer path sums per storey).
- Floor-plan rooms, doors and windows: the floor-plan lane reads those.
- A trained MEP symbol detector: there is no labelled MEP picture data. Only one public set was found, an
  electrical one (DELP: 45 scans, 34 classes, CC BY 4.0, [arXiv 2508.10449](https://arxiv.org/abs/2508.10449)). It
  can be a later real-picture check, not training data for v1.

## Inputs

A page reaches this lane when triage says so:
- `Sheet.discipline` (`app/core/ingest/model.py`, from `discipline_from_sheet`) is one of `plumbing`, `heating`,
  `ventilation`, `electrical`, `fire` or `structural`, which it is only by a strong title word or a sheet code
  (`discipline.py`; weak words such as "pump" or "post" never override the kind);
- `Sheet.kind == "mep_plan"` alone does **not** route: an `mep_plan` whose title names no service (discipline None)
  is not routed. Measured on the labelled set: the sheet-kind model calls 4 of 22 labelled floor plans
  (evacuation-plan photos) `mep_plan`, so routing on the kind would send floor plans to this lane;
- and `Sheet.decision != "set_aside"`.

A page the sheet-kind step gave **no reply** for (triage off, as on the no-keys backend) is routed by its file name
instead (AC-20): `discipline_from_sheet("mep_plan", <file stem>, None)`, so only a sheet code or a strong word names
the service ("H-101 Floor 1 heating.png"); a weak word ("pipe layout 7.png") or none leaves the file as it was. A
reply always wins, even one with no discipline. Each fact read this way says so in its `source`, after its readers
(`picture:template+mask:discipline-from-file-name`), and stays Low like every picture fact.

The page is one of:

| Page | Lane | What is read |
| --- | --- | --- |
| raster scan, PNG/JPEG/TIFF | picture | the image, after ingest's normalise stage |
| camera photo (`photo_plan`) | picture | the image after `RECTIFIER=r3` |
| vector PDF (drawn) | parse exactly + picture check | page 1's paths and text (`vector_pdf/objects.py`) **and** its render |
| scanned PDF (no vector paths) | picture | the render |

An IFC model never reaches this lane: it gets `facts_mep` / `facts_arch` directly.

## Outputs

One `FactSheet` per page, keyed by the **drawing id**, never by a file stem. Nothing in it says IFC.

```python
FactSheet(
    model="<drawing id>",                      # the id ingest gave the drawing; an opaque key
    disciplines=["heating"],                   # those of the facts, most facts first
    facts=[
        Fact(topic="space_heater.count", subject="all", value=12, unit="count",
             storey="2. krs", discipline="heating", source="picture:vlm+template",
             spots=(Spot(page=1, box=(0.41, 0.22, 0.43, 0.24), reader="vlm+template"), ...)),
        Fact(topic="space_heater.count", subject="Radiator 22-600", value=9, unit="count", ...),
        Fact(topic="pipe_segment.length", subject="all", value=38.5, unit="m", system="heating",
             discipline="heating", source="picture:vlm+mask", spots=(...)),
        Fact(topic="pipe_segment.size_length", subject="DN20", value=9.9, unit="m", system="heating", ...),
    ],
)
```

- **Topics are the IFC fact sheet topics** (ifc-mep report, `facts_mep.py`): `<kind>.count` (subject `all`, or the
  legend label as printed), `<kind>.length` and `<kind>.with_length` (m, count), `<kind>.size_length` (subject =
  the printed size), `category.count` (subject = the legend group heading, when the legend has groups). A legend
  label maps to a kind with `kind_of` (below). A label that maps to no kind gets topic `symbol.count`, with the
  label as the subject.
- **`source`** names the method: `picture:<readers>`, e.g. `picture:vlm+template`, `picture:vlm` (one reader only),
  `vector:paths+vlm`, `picture:vlm+mask` (lengths). The answer layer finds the route from the prefix before the colon
  (`picture` or `vector`).
- **`spots`**: one per counted thing (a symbol's box), or one per run piece (a line segment's box), as page
  fractions. The viewer shows them as the answer's marks, and the double-check shows the disputed ones. This is
  an additive field on `Fact` (default `()`, so IFC facts are unchanged). Its owner is ifc-arch, through the
  orchestrator (open decision 1).
- **`storey`**: the storey the sheet's title names (`Sheet.title`, the same words `discipline.py` reads), else
  None. Never guessed from the content.
- A thing nobody looked for has **no fact**, never a 0. A count of 0 is written only when the legend lists the
  symbol and both readers looked for it on the whole plan and found none.
- With the facts, the lane hands back a `Checked` (below) for `answer.check`: the disputed places, at most 5,
  strongest first.

## Method

It mirrors the floor-plan scan path: read with several readers → double-check → facts, with the confidence of
decision 0011.

### 1. Read (adapters)

| Step | How | Reuses |
| --- | --- | --- |
| scale | the printed ratio + the scale bar's ticks; the file's own DPI only as `trusted_dpi` says. No estimate from doors: on a services plan the doors are background and often greyed out. | `PrintedReader` (`printed_scale/carbon.py`), `printed.printed_scale` |
| legend | one VLM call on the whole page: the legend's entries, each with its label as printed, its group heading, whether it is a symbol or a line style, and the symbol's box on the page. | the Carbon reader's client, image encoding and cache (`carbon/reader.py`, `contract.py` `sent_size`, `request_body`, `cache_name`, `price`) |
| symbols, reader A (`vlm`) | the VLM reads each tile of the plan and returns one box per instance of each legend label, plus the label. Tiles and the cross-tile dedupe are Carbon's (`tile_plan`, `TILE`, `OVERLAP`, `SAME`, `MAX_TILES`, `MAX_ITEMS`). | Carbon tiles; `openvlm` for the EU provider |
| symbols, reader B (`template`) | local, no model call: each legend symbol's crop is matched over the page (normalised cross-correlation at 0°/90°/180°/270° and three scales around the legend's). Peaks above the threshold become boxes, after non-maximum suppression. | numpy + PIL (installed); no new dependency |
| symbols, vector PDF (`paths`) | identical path groups (same commands up to translation and rotation, same stroke) repeated on page 1 are one symbol. A group whose shape equals a legend symbol's paths takes its label. | `vector_pdf/objects.py` |
| runs (`mask`) | for each legend *line* entry with a colour or dash pattern of its own: a mask of that style → skeleton → length in px × m/px; the size labels printed along the run (VLM tile reply) split it per size. | printed scale above |
| runs, vector PDF (`paths`) | the length of the paths drawn in the legend line's stroke (colour, width, dash), in PDF points × m/pt. | `vector_pdf/scale.py` |

What each reader looked for is in its `read` (legend labels). A label that is not in `read` stays unknown. This is
the `Extracted.read` rule of the floor-plan lane.

### 2. Double-check (core, pure)

Two readers per thing counted, as the floor-plan lane's second counter:
- symbols: `vlm` against `template` (picture) or against `paths` (vector PDF);
- runs: `mask` against the VLM's own length estimate per system (or `paths` for a vector PDF).

Matching: two spots are the same thing when their centres are closer than `near` (default 0.6% of the page
diagonal, about one symbol width on an A1 sheet at 150 dpi; tuned on bench dev only). Per label:
- **agree**: equal counts, and at least 90% of the spots matched one to one;
- **dispute**: anything else. The disputed places are the unmatched spots, each with one line per reader
  (`readers: {"vlm": "a radiator", "template": "nothing"}`) as `check.disputed` (double-check.md, Data). The
  value is reader A's (or `paths` on a vector PDF), until the bench decides which reader leads (AC-16).
- a run agrees when the two lengths are within 10%.

### 3. Facts (core, pure)

`picture_facts(drawing, checked)` turns the checked reading into `Fact`s with the topics above. A kind's `all`
count is the sum over its labels. A length needs a scale: without one there is no length fact, and the reason goes
into `notes`.

### 4. Confidence (decision 0011, no new mechanism)

- The routes are `picture` and `vector`. Their level comes from `route_levels` in the check policy
  (`level_of(..., sure=False, route=...)`, unchanged). Until a policy file names them, every answer from this lane
  is **Low**, basis `unrated`, with `level_of`'s own text.
- A disputed value is Low, basis `held`, whatever the route level.
- The bar to name a route Medium in the policy is AC-16 (bench) plus AC-17 (real sheets). **High is not given in
  v1**: a synthetic bench cannot certify, and we have no labelled real MEP sheets.

## Fixed signatures and ports

```python
# app/core/picture_facts.py: pure (no PIL, no ifcopenshell, no settings)
class Spot(Frozen):                 # also imported by ifc_facts.Fact.spots
    page: int
    box: Box                        # page fractions, app/core/drawing/model.py
    reader: str

class LegendEntry(Frozen):
    label: str                      # as printed
    group: str | None               # the legend's heading, e.g. "Heating"
    line: bool                      # a line style (a run), not a symbol
    box: Box | None                 # where the symbol is drawn in the legend

class Sighting(Frozen):
    label: str                      # a LegendEntry.label, or the reader's own words without a legend
    spot: Spot

class Run(Frozen):
    label: str
    size: str | None                # printed size, e.g. "DN20", "Ø125"
    length_m: float
    spots: tuple[Spot, ...]

class PictureReading(Frozen):
    reader: str                     # "vlm", "template", "paths", "mask"
    legend: tuple[LegendEntry, ...] | None   # None: no legend found
    read: tuple[str, ...] | None    # labels looked for; None: every legend label
    sightings: tuple[Sighting, ...] = ()
    runs: tuple[Run, ...] = ()
    storey: str | None = None
    notes: tuple[str, ...] = ()
    cost_usd: float = 0.0

class Checked(Frozen):
    readings: tuple[PictureReading, ...]
    agreed: dict[str, bool]         # label -> agree
    disputed: tuple[Disputed, ...]  # app/core/review/check.py Disputed (mark_id None), ≤ 5, strongest first

def kind_of(label: str, group: str | None) -> tuple[str, Discipline] | None: ...
def double_check(first: PictureReading, second: PictureReading | None, near: float = 0.006) -> Checked: ...
def picture_facts(drawing: str, checked: Checked) -> FactSheet: ...

# app/core/pipeline/ports.py: one new port
class PictureReader(Protocol):
    def read(self, source: DrawingFile, sheet: Sheet) -> PictureReading: ...
```

- `kind_of` is a word table in the dataset's languages (EN, FI, DE, SV, NL, ES, FR, IT, ET), as `discipline.py`.
  It maps a label to an IFC kind in snake case, as `facts_mep` writes it, and that kind's discipline. The group
  heading breaks ties ("valve" under "Heating" → heating).
- Readers raise nothing on a model failure. They return `read=()` and the reason in `notes`, as `raster_remote`
  does.

## Settings (all off by default)

| Setting | Values | Default |
| --- | --- | --- |
| `DISCIPLINE_PICTURES` | `off`, `template`, `glyphs`, `gemini` | `off` (the lane writes nothing; triage is unchanged) |
| `DISCIPLINE_GLYPHS_MODEL` | a folder with `model.onnx` (never committed) | `../data/models/pic-glyphs` |
| `DISCIPLINE_PICTURES_CACHE_DIR` | a folder | `../data/cache/discipline-pictures` |
| `DISCIPLINE_PICTURES_PROVIDER` | `gemini`, `eu` (openvlm) | `gemini` |
| `DISCIPLINE_PICTURES_MAX_USD` | USD per page | `0.15` |
| `DISCIPLINE_PICTURES_NEAR` | fraction of the page diagonal | `0.006` |

Only `app/settings.py` reads them, and only `app/composition.py` builds the readers.

Built (2026-11-15, brief pic-1, local readers only, no VLM): `DISCIPLINE_PICTURES=template` wraps the raster
extractor in `PictureLane` (`app/adapters/discipline_pictures/lane.py`). The drawing model passes through unchanged.
A page triage names a routed discipline (and does not set aside) gets its legend and printed scale read by the local
OCR (`legend.py`: the block under a "Legend" header; ink left of a label is its sample; a label with no ink is a
group heading), symbols by `template`, coloured runs by `mask` (a run's size from its legend label). The `FactSheet`
is kept by the page file's sha256 and is the `FactSource` the answers read (`composition._facts`). One reader per
label, so every fact is held: Low, never sure. Facts are written sheet-wide (no storey, no system) plus the
title's storey and each system's copies, so the fact answers (`answering/facts.py`) find them. A class the legend
does not list is refused ("not read on this picture"), not 0. Not wired yet: vector PDFs (triage gives them no
`Sheet`), the product's ask (it reads no fact sheet; only `Pipeline.answer_questions` does), the VLM readers.

Built (2026-11-15, pic-det): two more symbol readers, each with its own sheet folder (`lane.kept_in`).
`DISCIPLINE_PICTURES=gemini` (`gemini.py`, reader `vlm`): one Carbon call per page reads the legend's rows and every
plan occurrence's box; replies cached by page sha256 + prompt hash + model; a failed call or a reply that is not the
asked JSON raises, so the lane keeps no sheet (and keeps the one it had). `DISCIPLINE_PICTURES=glyphs` (`glyphs.py`):
a YOLO26 S glyph-style detector (72 classes: shape x fill x printed number) on 1024 px tiles, the legend binding
style -> label. Measured on a held-out rendered building (rwth-digitalhub v2, 36 pages, 1,155 symbols; trained or
tuned on bsc-clinic only; IoU 0.5):

| reader | P | R | counts within 10% | valves P/R | cost/page |
| --- | --- | --- | --- | --- | --- |
| template, OCR legend | 0.07 | 0.29 | 8/54 | 0.04/0.06 | 0 |
| glyphs, OCR legend | 0.92 | 0.38 | 9/54 | 0.80/0.24 | 0 (1.5 s CPU) |
| glyphs, true legend boxes (bound) | 0.96 | 0.82 | 27/54 | 0.83/0.29 | 0 |
| gemini (reads its own legend) | 0.95 | 0.92 | 46/54 | 0.80/0.68 | $0.030 |

The OCR legend reader is what sinks both local readers on scans (template 0.01/0.01, glyphs 0.77/0.06 there).
One synthetic building, legend always printed: not a pass on real sheets, so the facts stay Low.

## Cost per page

- Budget: **at most $0.15 per page**, enforced by `SpendGuard` per page (`spend.py`). A page that would exceed it
  stops tiling, and the labels on the tiles not read are left unknown, never 0.
- Calls: 1 legend call on the whole page, plus at most `MAX_TILES` tile calls. The printed scale is read once and
  shared with the floor-plan lane when both run. `template`, `mask` and `paths` are local (CPU, no cost).
- The cost is measured on the bench (AC-18). If the median page goes over $0.05, the tile count is cut before the
  budget is raised.

## Failure cases

| Case | What happens |
| --- | --- |
| no legend found | sightings take the VLM's own words; `kind_of` maps them when it can. `source` gets `:no-legend`. `template` cannot run (it has no crops), so every count has one reader and is held (Low, basis `held`) with the reason "no legend on the sheet". |
| legend label maps to no kind | `symbol.count` with the label as subject: answerable by the label's words, not by a kind. |
| no scale (no ratio, no bar, no trusted DPI) | counts only; no `.length` facts. A length question is refused with "the sheet has no scale". |
| not to scale (printed NTS) | as no scale. |
| VLM error, timeout or budget hit | that reader's `read` is `()` or partial. One reader left: held, Low. None: no facts, and the notes say why. |
| too many tiles (> `MAX_TILES`) | the symbols are not read; the legend and scale are kept; notes say so. |
| photo the rectifier could not flatten | read as is; template matching is off (perspective breaks it), so a single reader, Low. |
| several storeys on one sheet | `storey` None. Facts are per sheet. |
| a symbol in the legend but not on the plan | counted as 0 only when both readers looked over the whole plan (see Outputs). |

## Benchmark (there is no labelled MEP picture data)

**Ground truth from the dataset's own models.** Four buildings in the dataset have service or structural IFC
models besides the architectural one. For each model and each storey, a renderer draws one **plan picture per
discipline**:
- every distribution element of that discipline in the storey, projected to plan (`ifcopenshell.geom` world
  coordinates, XY);
- terminals and equipment as one symbol per legend label (type name: a shape, a fill, past 24 labels a number
  beside it) at the centre of the element's plan box; structural plans draw columns, footings and piles the same
  way; fittings are not drawn;
- segments as lines along their plan axis, styled per system (colour and dash), with the size printed along runs
  longer than 2 m;
- a background from the same building's architectural model (walls cut at 1.2 m, light grey), where the two
  models share coordinates (checked by the storey elevations and the bounding boxes overlapping);
- a legend (symbol + label, grouped by system), a scale bar and the ratio printed (1:50 to 1:500, the first that
  fits an A1 sheet), and a title naming the storey and the discipline.

Built (P3): `app/adapters/ifc_model/plan_picture.py`, `python -m app.cli disc-bench render --model <services.ifc>
--background <architecture.ifc> --out <dir> --dpi 100 150 200 --variant clean scan photo no-legend no-scale`
writes `<dir>/<variant>-<dpi>/<model>--<storey>--<discipline>.png|jpg` and a truth `.json` beside each.

IfcConvert's SVG serializer can keep only chosen classes (`--include entities`) and cut storeys by section height
([IfcConvert.cpp](https://github.com/IfcOpenShell/IfcOpenShell/blob/master/src/ifcconvert/IfcConvert.cpp)). It
draws no symbols, labels or legends, though, so the renderer draws its own layer. It may use IfcConvert for the
architectural background only.

**Truth** = the fact sheet of the same model, restricted to the storey: `<kind>.count` per type name (the legend
label is the type name), `<kind>.length` per system, and `<kind>.size_length`, from `facts_mep`. Every truth thing
also has its plan point, so symbol recall can be scored. An element the geometry kernel cannot build is not drawn
and is left out of the truth (`undrawn`). A run has two lengths: `length_m` (the fact sheet's) and `plan_m` (what
the plan shows; a riser is near 0 there); a reader measures `plan_m`, P4 scores against it.

**Variants** (seeded, so a picture can be rebuilt bit for bit):
- resolution: 100, 150 and 200 dpi at the printed scale;
- degradation: `clean`; `scan` (greyscale, Gaussian blur σ 1 px, JPEG quality 60, rotation ±1.5°, 0.2% salt
  noise); `photo` (corners moved in by ≤ 5% of the side, light falling off by ≤ 30%; goes through `RECTIFIER=r3`);
- `no-legend` and `no-scale` copies, for the failure cases (the renderer draws them for every picture; the manifest
  uses 10%).

**Split by building**: two buildings dev, two test, chosen so that each discipline appears in both splits where the
data allows. The list is fixed in the bench manifest (gitignored, `data/stoa/disc-bench/manifest.json`), before
any reader runs. Tuning (`near`, template threshold, prompts) only on dev. Test is scored once per milestone, as
`--against eval` in `eval/`.

**Real sheets**: Bogdan's hard slice (docs/GOLDEN.md, "The hard slice": 48 sheets labelled by eye, ranges
`[lo, hi]`). Its MEP and structural sheets are scored by his side with `stoa_eval hard` (share of counts inside
their range), plus discipline accuracy against `Sheet.discipline`.

**Metrics** (per discipline and per variant):
- **count exact**: the share of (picture, label) units whose count equals the truth;
- **count ±1**: the same, within one;
- **symbol recall / precision**: a predicted spot matches a truth point within `near` (one to one, greedy by
  distance);
- **length within 5% / 10%**: the share of (picture, system, size) runs;
- **agreed share** and **exact when agreed**: the double-check's gate;
- **refusals**: the share of units with no fact;
- **cost**: USD per page, median and p95; seconds per page.

A reader's output for the bench is one JSON line per picture: `{"picture": <the truth file's picture>, "sheet":
<its FactSheet, facts with spots>, "agreed": {label: bool} (the double-check's), "cost_usd": float, "seconds":
float}`; `stoa_eval disc-pictures <bench dir> <lines>` scores it.

Each scored run writes a record to `eval/results/disc-pictures/runs/` (aggregates only, no file names), not
`eval/results/runs/`: `stoa_eval history` reads every file there as an answering record, and this record's shape
would break it.

## Files owned (future workers)

| Worker | Files |
| --- | --- |
| P1 core | `backend/app/core/picture_facts.py`, `backend/tests/test_picture_facts.py`; the `PictureReader` port in `app/core/pipeline/ports.py` (one class) |
| P2 readers | `backend/app/adapters/discipline_pictures/` (`__init__.py`, `legend.py`, `vlm.py`, `template.py`, `mask.py`, `paths.py`), `backend/tests/test_discipline_pictures*.py` |
| P3 bench render | `backend/app/adapters/ifc_model/plan_picture.py`, `backend/tests/test_plan_picture.py`, its `app.cli` subcommand `disc-bench render` |
| P4 bench score | `eval/stoa_eval/disc_pictures.py`, `eval/tests/test_disc_pictures.py`, the `stoa_eval disc-pictures` subcommand |
| integration (orchestrator / Bogdan) | `app/settings.py`, `app/composition.py`, `.env.example`, ingest's call into the lane, `Fact.spots` in `app/core/ifc_facts.py` (ifc-arch), the answer path's `source` → route (ifc-ask) |

## Acceptance criteria

Unit tests use hand-written readings, synthetic images drawn with PIL in the test, and a synthetic IFC built with
`ifcopenshell.api`. No dataset file appears in a test.

Core (P1):
- **AC-1** `kind_of`: "Radiator", "Heizkörper", "lämpöpatteri" → `("space_heater", "heating")`; "Supply air
  diffuser" → `("air_terminal", "ventilation")`; "Socket outlet 2x" → `("outlet", "electrical")`; "Valve" with group
  "Heating" → `("valve", "heating")`, with group "Cold water" → `("valve", "plumbing")`; "Logo" → None.
- **AC-2** `double_check` on two readings of label L, 10 spots each, 9 within `near` of each other: L agreed; the 1
  + 1 unmatched spots are the disputed places, each with both readers' sentences; at most 5 disputed, strongest
  (highest-scoring reader A spot) first.
- **AC-3** `double_check` with `second=None`: nothing agreed; disputed is empty, and every fact is held (AC-7).
- **AC-4** `picture_facts` writes `<kind>.count` subject `all` (the sum of the kind's labels) and one per label, unit
  `count`, `source` `picture:<readers>`, one `Spot` per sighting, and `model` = the drawing id passed in.
- **AC-5** A label not in a reader's `read` yields no fact. A label read by both, with no sightings, yields a count of
  0. A label read by one reader yields its count, held.
- **AC-6** Runs: with `length_m` given, `<kind>.length` (m) per system, `<kind>.size_length` per printed size, and
  `<kind>.with_length` (count of runs). A reading whose scale note says no scale yields no length fact.
- **AC-7** The level (the answer path's mapping, tested through `level_of` as it is, `sure=False` always): with a
  policy that does not name route `picture`, an answer from these facts is Low, basis `unrated`. A disputed or
  single-reader label's answer is `held`: Low, basis `held`. With `route_levels={"picture": "medium"}`, an agreed
  answer is Medium, basis `route`.
- **AC-8** `tests/test_architecture.py` passes: `picture_facts.py` imports no adapter, PIL, ifcopenshell or
  settings.

Readers (P2):
- **AC-9** `template` on a 2000×1400 synthetic page (PIL-drawn: a legend with 3 symbols, 25 placed instances, rotated
  0/90/180/270): finds all 25, labels each right, no false positives on the legend itself.
- **AC-10** `vlm` with a fake client: two overlapping tiles reporting the same symbol give one sighting (Carbon's
  `SAME` rule). A reply over `MAX_ITEMS` is a failed tile: its labels leave `read`. A client error gives `read=()`
  with the reason in `notes`, and nothing raises.
- **AC-11** `paths` on a synthetic vector PDF (drawn in the test) with 6 copies of one symbol (3 rotated) and two
  line styles: 6 sightings of the legend's label; each line style's length within 0.5% of the drawn length.
- **AC-12** `mask` on a synthetic raster with a 5.00 m red run at a known m/px: length within 3%. Without a scale:
  no run, note "no scale".
- **AC-13** The budget: with `DISCIPLINE_PICTURES_MAX_USD=0.01` and a fake client charging $0.004 a call, at most 2
  calls are made. The tiles not read leave their labels unknown.
- **AC-14** `DISCIPLINE_PICTURES=off`: composition builds no reader, ingest output is byte-identical on the sample
  project.
- **AC-20** No sheet-kind reply: `H-102 heating plan.png` is read and its facts' `source` names the file name
  (`test_a_picture_no_sheet_kind_step_saw_is_routed_by_its_file_name`); `pipe layout 7.png` is not
  (`test_a_file_name_that_names_no_discipline_leaves_the_picture_unread`); off, the same upload gives the same
  routes, flags and drawings and no fact sheet (`test_off_the_file_name_changes_no_route_flag_or_drawing`).

Bench (P3, P4) and measured bars:
- **AC-15** The renderer, on a synthetic IFC (one storey, 4 space heaters, 2 pipe systems with known lengths):
  the picture's truth file lists 4 heater points (each within 1 px of the projected centre), the two system lengths
  equal the `facts_mep` lengths, and the legend has one entry per type name. The same seed gives identical bytes.
- **AC-16** Leaving Low (bench → `route_levels.picture = medium`): on the **test** split, variants clean + scan at
  150 dpi, among (picture, label) units the double-check agreed on: count exact ≥ 90%, with the Wilson 95% lower
  bound ≥ 85% and ≥ 60 units. Symbol recall ≥ 90%. Length within 10% ≥ 80% on ≥ 30 runs. The record is committed,
  and reader A vs `template` as the leading reader is decided on dev before the test read.
- **AC-17** Real sheets: on the hard slice's MEP/structural sheets (Bogdan's side), the counts this lane answers
  are inside their by-eye range at least as often as the floor-plan lane's counts are on the same sheets today, and
  no answer on a sheet set aside by triage. Below that, the route stays Low whatever AC-16 says.
- **AC-18** Cost: median ≤ $0.05 and p95 ≤ $0.15 per page on the bench test run; no page over the budget.
- **AC-19** Public repo: no committed file contains a dataset file name, question text or answer. Each PR greps
  its diff for the file stems listed in the gitignored bench manifest, and the hit count must be 0.

## Implementation plan

1. **P1 core** first (AC-1..AC-8): the shapes every other slice codes against. About half a day for one worker.
2. **P3 bench render** in parallel with P1 (AC-15): it needs only `facts_mep` and ifcopenshell.
3. **P2 readers** after P1 (AC-9..AC-14): `template` and `paths` first (local, free), then `vlm` and `legend`,
   then `mask`.
4. **P4 bench score** after P3 (AC-16, AC-18 measured). It runs dev until the knobs settle, then test once.
5. Integration (orchestrator with Bogdan): `Fact.spots`, settings, composition, ingest's call, and the answer path's
   route from `source`. Then AC-17 on Bogdan's side.

## Open decisions

1. `Fact.spots` on the shared `Fact` (recommended: additive, default `()`), or a separate `marks` map beside the
   `FactSheet`. Owners: ifc-arch, Tudor.
2. The VLM for the picture readers: Carbon (`gemini-4-carbon`, as the floor-plan hard path) or the EU open model
   (`openvlm`). The spec runs either; the bench decides on dev. Owner: Bogdan.
3. Whether a vector PDF's `paths` reading is certified like the vector floor-plan route (decision 0011 "a certified
   route is High"), or measured first like `picture`. Recommended: measured first, since symbol grouping is new.
   Owner: Tudor.
4. Where the lane runs: in ingest after triage (cost at upload), or on the first question to a sheet. Recommended:
   ingest, as `facts_mep`. Owner: Bogdan.

## Prior art (checked 2026-11-14)

- No public HVAC/MEP symbol benchmark with standard metrics was found. Electrical: DELP, above. P&ID: a synthetic
  set of 500 drawings ([arXiv 2109.03794](https://arxiv.org/abs/2109.03794)). Architecture: FloorPlanCAD, 30
  categories, unmaintained since 2022 ([site](https://floorplancad.github.io/)).
- VLM symbol reading on engineering blueprints, BlueprintSymVL
  ([record](https://research.chalmers.se/en/publication/549362)): the authors report clutter, look-alike distractors
  and hallucinated symbols, and judge VLMs not ready for autonomous use. That is why a second, local reader checks
  every VLM count.
- Counting falls as scenes grow busier: on VLMCountBench, Gemini 2.5 Flash drops from 0.58 to 0.30 between levels
  1 and 3 ([arXiv 2510.04401](https://arxiv.org/html/2510.04401v1)). That is why the plan is read in tiles with
  boxes per instance, not as one count per page.
