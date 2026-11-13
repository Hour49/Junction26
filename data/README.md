# data/

Local data for the project. **Nothing here is committed** except this README and `.gitignore`: partner data stays
out of the public repo (Junction Terms §8.4, docs/ENGINEERING.md §4). Don't upload it anywhere else either until we
know Stoa's data rules.

## Stoa datasets

| Set | Zip | Unzipped into |
| --- | --- | --- |
| preview (0.5 GB) | `stoa/downloads/junction-dataset-preview.zip` | `stoa/preview/` |
| full (9.8 GB) | `stoa/downloads/junction-dataset.zip` | `stoa/full/` |

Get them:

1. Put the two links in your clone's `.env` (gitignored) as `STOA_PREVIEW_URL=...` and `STOA_FULL_URL=...`. The links
   are in the Stoa challenge brief; ask Bogdan if you don't have them.
2. Run `python3 tools/fetch_stoa_data.py preview` (or `full`, or `all`) from the repo root. It needs about twice the
   zip's size free, resumes an interrupted download when rerun, and never overwrites an unzipped folder (delete it
   to unzip again).

What's inside (from the dataset's own README, 2026-11-06): about 14,000 drawings (PDF, DWG, DXF, IFC, SVG, PNG,
JPEG scans) in about 30 languages, under `data/<source>/`, and `questions.jsonl` with about 120,000 quantity-takeoff
questions (`path`, `question`, `answer`, `unit`, `type`) for roughly 40% of them. Types: count, area, length,
volume, text. Their scoring: counts exact; areas, lengths and volumes within 2%; text free-form. Sources include
CubiCasa5K, Swiss Dwellings, IFC models, US historic survey drawings (HABS), Helsinki City Archives (Finna) and
European museum archives. **For non-commercial use in the Junction challenge**; every file keeps its own licence and
credit in `data/<source>/LICENSE.md` (some NC, SA or ND): keep the credit when a drawing is shown in the demo.

Other folders: `stoa/labels/` for our hand-labelled real pages (golden case 2, docs/SPEC.md §6).
