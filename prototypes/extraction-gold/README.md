# extraction-gold: build the Part 1 gold for the golden set

These scripts write the gold extraction for golden v2 Part 1: one `extraction_v1` JSON per drawing file
([decision 0004](../../docs/decisions/0004-extraction-format.md), schema in `eval/schemas/`). Each one reads a source's
own truth, not the drawing image, so the gold says what a perfect pipeline would extract. The gold files go to the
gitignored `data/stoa/extraction_gold/<source>/`; nothing from the dataset is committed. They were written on
2026-11-13 during the golden-set work.

| script | truth from | files written | rule check (gold reproduces the dataset answers) |
| --- | --- | --- | --- |
| `cubicasa_gold.py` | public CubiCasa5K `model.svg`, dev images only; eval images get `truth: counts` from their question answers (decision 0003) | 4,787 (3,828 dev, 959 eval) | 11 count families 100%; saunas 2,648 / 2,655. Every dev image has a scale: 30 measured (two checks), 3,787 estimated (annotation unit and door widths, within 10% of each other on 72%), 11 not to scale with an estimate; every dev room has an area (113 printed, exact; the rest estimated). The 10 eval images in golden v2 have scales read from the image only |
| `swiss_gold.py` | the dataset's DXF, fitted to the PDF page (residual 0.00 pt), written for the PDF and the PNG of each plan | 2,080 (831 + 209 per format) | counts 25,562 / 25,568, areas 12,012 / 12,016 |
| `opening_design_gold.py` | the sheets' PDF text layer (pdfplumber, ruling lines per cell), checked against renders; header rows by hand | 3 (2 dev, 1 eval): 7 schedule tables with `truth: tables`, plus 9 fixtures on A-701 | 64 / 64 |
| `conflicts_gold.py` | the ifc_models, swiss and CubiCasa gold above plus the PDF text and hand-measured dimension lines; dev split only | `_conflicts/conflicts.jsonl` (62 files), `_conflicts/extras.jsonl` (12 Part 2 lines), 14 overlays in `_overlays/conflicts/` | 14 real conflicts (ifc_models: drawn vs IFC counts), 102 agree entries |
| `ifc_gold.py` | the IFC model (classes, storeys, quantities) placed by the plan SVG, which shares the PDF sheet's frame | 69 (46 dev, 23 eval) | every count, area, length and volume family 100% (columns 22 / 22); 88 model-level questions out of scope |

`ifc_gold.py` needs ifcopenshell (LGPL-3.0-or-later), allowed as an unmodified dependency by
[decision 0006](../../docs/decisions/0006-lgpl-dependencies.md).

## Run

Get the dataset (see [data/README.md](../../data/README.md)) and, for CubiCasa, the public CubiCasa5K zip (Zenodo
record 2613548, CC BY-NC-SA 4.0, into `data/external/cubicasa5k/`). Then, from the repo root:

```bash
uv run prototypes/extraction-gold/cubicasa_gold.py --dataset data/stoa/full/junction-dataset \
    --split data/stoa/split --out data/stoa/extraction_gold/cubicasa5k --check
uv run prototypes/extraction-gold/swiss_gold.py --dataset data/stoa/full/junction-dataset \
    --split data/stoa/split --out data/stoa/extraction_gold/swiss_dwellings
uv run prototypes/extraction-gold/ifc_gold.py --dataset data/stoa/full/junction-dataset \
    --split data/stoa/split --out data/stoa/extraction_gold/ifc_models
cd eval && uv run python -m stoa_eval validate-extraction ../data/stoa/extraction_gold/cubicasa5k
uv run prototypes/extraction-gold/opening_design_gold.py   # schedule tables of the 3 opening_design sheets (default paths)
# conflict cases (reads the gold written above; judgements are data inside the script)
uv run prototypes/extraction-gold/conflicts_gold.py
```

Each script pins its own dependencies (PEP 723). No PyMuPDF, no Ultralytics.

## Scale

Every file carries a `scale` object: `scaled`, `no_scale` or `not_to_scale`, with the evidence the sheet shows
(`scale_text`, `scale_bar`, `printed_areas`, `dimension_lines`, `not_to_scale_note`). An exact gold scale needs two
independent checks within 1%. Swiss: title block, checked against the scale bar and printed room areas (1,648
checks, max 0.88%). CubiCasa: 20 dev plans scaled by hand from printed room areas or dimension lines, 10 marked not
to scale, 33 looked at with no evidence; the rest are marked "scale not reviewed" and stay out of the scale cases.
CubiCasa dev files without a scale carry `reference_m_per_unit` from the annotation unit (about 1 cm, within about
8% of the hand scales), used only to measure best-effort estimates.

## Known limits

- Elements annotated twice at the same spot in CubiCasa are one gold object with `attrs.multiplicity = 2`; the
  12 questions whose answers count them twice are tagged suspect.
- Swiss gold lists doors, windows, toilets, sinks, showers and bathtubs, not kitchen blocks, stairs or columns; the
  scorer leaves classes a source's gold never lists unscored.
- One CubiCasa sheet (`high_quality_architectural-10022`) prints "1:50" for a detail, not the plan: kept as a trap.
