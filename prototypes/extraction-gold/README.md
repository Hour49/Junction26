# extraction-gold: build the Part 1 gold for the golden set

These scripts write the gold extraction for golden v2 Part 1: one `extraction_v1` JSON per drawing file
([decision 0004](../../docs/decisions/0004-extraction-format.md), schema in `eval/schemas/`). Each one reads a source's
own truth, not the drawing image, so the gold says what a perfect pipeline would extract. The gold files go to the
gitignored `data/stoa/extraction_gold/<source>/`; nothing from the dataset is committed. They were written on
2026-11-13 during the golden-set work.

| script | truth from | files written | rule check (gold reproduces the dataset answers) |
| --- | --- | --- | --- |
| `cubicasa_gold.py` | public CubiCasa5K `model.svg`, dev images only; eval images get `truth: counts` from their question answers (decision 0003) | 4,787 (3,828 dev, 959 eval) | 11 count families 100%; saunas 2,648 / 2,655 |
| `swiss_gold.py` | the dataset's DXF, fitted to the PDF page (residual 0.00 pt), written for the PDF and the PNG of each plan | 2,080 (831 + 209 per format) | counts 25,562 / 25,568, areas 12,012 / 12,016 |

The IFC script (`ifc_gold.py`, 69 sheets from the IFC model and the plan SVG) needs ifcopenshell (LGPL-3.0-or-later)
and is added once that licence question is decided.

## Run

Get the dataset (see [data/README.md](../../data/README.md)) and, for CubiCasa, the public CubiCasa5K zip (Zenodo
record 2613548, CC BY-NC-SA 4.0, into `data/external/cubicasa5k/`). Then, from the repo root:

```bash
uv run prototypes/extraction-gold/cubicasa_gold.py --dataset data/stoa/full/junction-dataset \
    --split data/stoa/split --out data/stoa/extraction_gold/cubicasa5k --check
uv run prototypes/extraction-gold/swiss_gold.py --dataset data/stoa/full/junction-dataset \
    --split data/stoa/split --out data/stoa/extraction_gold/swiss_dwellings
cd eval && uv run python -m stoa_eval validate-extraction ../data/stoa/extraction_gold/cubicasa5k
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
