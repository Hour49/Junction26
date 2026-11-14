"""Scans with a known scale, for fitting SCALE_CARBON_DOORS
(app/adapters/raster_scale/carbon_doors.py) on more than the one hard-set sheet it was first
measured on: each vector PDF's page 1, whose scale the pipeline read from its printed ratio and
bar, rendered at 100, 150 or 200 dpi and made
to look scanned (grey paper, blur, noise, a 0.5-2 degree tilt, a third turned 90 degrees, JPEG at
quality 55-65), so its metres per pixel are known exactly: m_per_pt x 72 / dpi.

    cd backend && PYTHONPATH=. uv run --locked python scripts/make_scans.py \
        --truth <run>/extraction [--truth ...] --files <list> \
        --dataset ../data/stoa/full/junction-dataset --out ../data/stoa/runs/<scans>

For every file in the list (dataset paths of PDFs) whose pipeline extraction under --truth is
`scaled`, it writes into --out:

- dataset/data/scans/<stem>.jpg: the scan (a dataset root: run `app.cli answer --dataset` on it);
- questions.jsonl: one door question per scan, the `answer` CLI's input;
- gold/<stem>.json: {"file", "pages": [{"width"}], "scale": {"m_per_unit"}}, the reference
  scripts/carbon_door_scale.py reads (metres across the page, so the image's own width);
- arm/<stem>.json: an extraction_v1 that looked for every element class and found none, the
  reading of a detector that found no door (RASTER_COMPONENTS=elements=dir:<out>/arm), so the
  sheet takes the path SCALE_CARBON_DOORS covers on a machine without detector models.

Rerunning the CARBON_DOOR_M fit (app/core/pipeline/raster_scale.py; 1.069 came from 26 dev scans):
pick dev-split floor plans (never eval or golden v2 files), run `app.cli answer` on the PDFs for
the truth runs, split the files into two halves BEFORE any Carbon run (fixed seed, by path), run
this script, then `app.cli answer` on --out's questions.jsonl and dataset/ twice, with
EXTRACTOR_RASTER=composite RASTER_COMPONENTS="elements=dir:<abs out>/arm,plans=one-plan"
RASTER_SCALE=priors CARBON_READER=large and SCALE_CARBON_DOORS=on (GEMINI_BUDGET_USD set; about
0.08 USD a sheet), then =off with GEMINI_BUDGET_USD=0 (cached replies only), and score:
`scripts/carbon_door_scale.py --off <off>/extraction --on <on>/extraction --gold <out>/gold`; fit
on half 1, count half 2 inside the band at that fit (the scale is proportional to the width).

Deterministic: every choice is seeded by the file's path. The scans are partner-derived: they stay
under data/ (gitignored), never in git.
"""

import argparse
import hashlib
import io
import json
import random
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageFilter

from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.core.drawing.model import ELEMENT_CLASSES, Drawing, Page, Scale

DPIS = (100, 150, 200)
PAPER = (232, 229, 221)  # a grey, slightly warm scanner background


def rng_of(path: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"scan:{path}".encode()).hexdigest(), 16))


def scanned(page: Image.Image, rng: random.Random) -> Image.Image:
    """`page` (white paper, black ink) made to look scanned."""
    grey = page.convert("L")
    paper = Image.new("RGB", grey.size, PAPER)
    ink = Image.new("RGB", grey.size, (40, 38, 36))
    image = Image.composite(paper, ink, grey)  # white -> paper, black -> ink
    image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.1)))
    noise = Image.effect_noise(grey.size, rng.uniform(10, 22)).convert("RGB")
    paper_tone = Image.new("RGB", grey.size, (235,) * 3)
    noise_tone = Image.new("RGB", grey.size, (20,) * 3)
    image = ImageChops.add(
        ImageChops.multiply(image, paper_tone), ImageChops.multiply(noise, noise_tone)
    )
    tilt = rng.uniform(0.5, 2.0) * rng.choice((-1, 1))
    image = image.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=PAPER)
    if rng.random() < 1 / 3:  # as the USCG sheet: turned a quarter
        image = image.transpose(Image.Transpose.ROTATE_90)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--truth", type=Path, action="append", required=True)
    parser.add_argument("--files", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    truths = [ExtractionV1Reader(folder) for folder in args.truth]
    files = [line.strip() for line in args.files.read_text().splitlines() if line.strip()]
    scans, gold = args.out / "dataset" / "data" / "scans", args.out / "gold"
    scans.mkdir(parents=True, exist_ok=True)
    gold.mkdir(parents=True, exist_ok=True)
    made: list[str] = []
    for index, path in enumerate(sorted(files, key=lambda f: rng_of(f).random())):
        drawing = next((d for t in truths if (d := t.drawing(path)) is not None), None)
        if drawing is None or drawing.scale.status != "scaled" or not drawing.scale.m_per_unit:
            print(f"skip {path}: no scaled vector reading")
            continue
        rng, dpi = rng_of(path), DPIS[index % len(DPIS)]
        pdf = pdfium.PdfDocument((args.dataset / path).read_bytes())
        page = pdf[0].render(scale=dpi / 72).to_pil()
        image = scanned(page, rng)
        stem = Path(path).stem
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=rng.randint(55, 65))
        (scans / f"{stem}.jpg").write_bytes(buffer.getvalue())
        file = f"data/scans/{stem}.jpg"
        m_per_px = drawing.scale.m_per_unit * 72 / dpi  # the vector reading is per PDF point
        truth = {"file": file, "pages": [{"width": image.width}], "scale": {"m_per_unit": m_per_px},
                 "made_from": path, "dpi": dpi}  # fmt: skip
        (gold / f"{stem}.json").write_text(json.dumps(truth, indent=1) + "\n", encoding="utf-8")
        made.append(file)
        print(f"{file}\t{dpi} dpi\t{image.width}x{image.height}\t{m_per_px * 1000:.2f} mm/px")
    with (args.out / "questions.jsonl").open("w", encoding="utf-8") as questions:
        for file in made:
            questions.write(json.dumps({"path": file, "question": "How many doors are there?"}))
            questions.write("\n")
    arm = ExtractionV1Writer(args.out / "arm", dict.fromkeys(made, "dev"))
    for file in made:
        with Image.open(args.out / "dataset" / file) as image:
            size = image.size
        arm.write(
            Drawing(
                file=file,
                pages=(Page(page=1, width=size[0], height=size[1], unit="px"),),
                scale=Scale(status="no_scale"),
                read=ELEMENT_CLASSES,  # looked for every class, found none
                notes=("stand-in detector: found nothing (scripts/make_scans.py)",),
            )
        )
    print(f"{len(made)} scans in {scans}")


if __name__ == "__main__":
    main()
