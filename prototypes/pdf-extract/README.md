# pdf-extract: answer Stoa questions from the drawing PDF alone

These are prototypes, not product code. Each script reads `questions.jsonl`, picks out the questions it can answer,
and writes one answer_v1 line per question ([decision 0002](../../docs/decisions/0002-answer-format.md)) with
evidence boxes. It reads only the PDF named in the question: no DXF, SVG or IFC sibling, and no model call.
They were written during the dataset review (2026-11-13) so that other workers can build on them rather than start
over.

| script | answers | measured on the full dataset |
| --- | --- | --- |
| `swiss_counts.py` | swiss_dwellings counts: rooms labelled X, apartments, doors, windows, toilets, washbasins, bathtubs, showers | 25,546 / 25,568 (99.91%), 6.4 s |
| `swiss_areas.py` | swiss_dwellings areas: room N.N, rooms labelled X, apartment X, floor total | 12,012 / 12,016 (99.97%), 23 s |
| `ifc_plan_areas.py` | ifc_models room areas and storey totals on plan PDFs | 1,806 / 1,862 (96.99%), 3.3 s |

## Run

Get the dataset first (see [data/README.md](../../data/README.md)), then from the repo root:

```bash
uv run prototypes/pdf-extract/swiss_counts.py --dataset data/stoa/full/junction-dataset --out swiss_counts.jsonl
```

Each script declares its own pinned dependencies (PEP 723), so `uv run` needs no project: pypdfium2, plus
shapely and pdfplumber where used. No PyMuPDF and no Ultralytics (AGPL). `--limit N` runs a quick subset.

## Per template

The numbers were measured with the dataset's rule (`stoa_eval.scoring.judge`: counts exact, areas within 2%).

| source | template | correct / handled |
| --- | --- | --- |
| swiss counts | rooms labelled X | 12,730 / 12,730 |
| | apartments | 2,080 / 2,080 |
| | doors | 2,080 / 2,080 |
| | windows | 2,064 / 2,080 |
| | toilets | 2,080 / 2,080 |
| | washbasins | 2,080 / 2,080 |
| | bathtubs | 1,788 / 1,794 |
| | showers | 644 / 644 |
| swiss areas | room N.N | 4,152 / 4,152 |
| | rooms labelled X | 2,034 / 2,034 |
| | floor total of numbered indoor rooms | 2,080 / 2,080 |
| | apartment X | 3,746 / 3,750 |
| ifc_models areas | room net floor area | 1,744 / 1,792 |
| | total of all rooms on a storey | 62 / 70 |

The rules that made the difference are in each script's docstring. Some of them:
- read every PDF text object on its own, because the page text joins overlapping labels
- treat a compound path as an outline plus holes
- read the scale from the sheet, because one IFC model is drawn at 1:200
- test window symbols against their own axis, because plans are rotated
- use fill colours as meaning: swiss grey 228 is outdoor and 243 is a lift, stair or shaft

## Limits

- **These numbers are not a held-out result.** The rules were found and tuned on all questions before the sealed
  20% eval split existed (Bogdan, 2026-11-13). Judge any change on the eval split, and tune on the dev split only.
- They rely on this dataset's drawing style: symbol stroke colours and widths, segment counts, fill colours. Another
  renderer of the same buildings would break them.
- Known misses:
  - swiss: stair flights counted as windows (8 floors); 3 floors where the dataset's bathtub answer is one above
    the tubs drawn; apartments spread over several outlines
  - ifc_models: a sheet that stacks storeys (gymzaal); rooms with holes that the PDF fill doesn't show (molio
    corridor); spaces of other storeys drawn without a storey prefix
- Not covered: cubicasa5k (raster images), ifc_models counts, volumes and lengths (IFC data, not drawn), wall areas
  (need heights), ifc_bench and opening_design.

## Licences

swiss_dwellings drawings are CC BY 4.0 (Archilyse AG). ifc_models drawings carry per-file licences (see the
dataset's `data/ifc_models/LICENSE.md`). The scripts contain no dataset content beyond the label words their rules
need. Put the credit line under any picture made from these drawings.
