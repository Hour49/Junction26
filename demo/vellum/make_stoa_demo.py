"""Stoa mode for the Vellum clickable demo: copy one real floor of the Stoa dataset into demo/vellum/stoa/.

Local only. The Stoa data is partner data and never gets committed: demo/vellum/.gitignore holds stoa/.

    python3 -I demo/vellum/make_stoa_demo.py --dataset ~/Junction26/data/stoa/full/junction-dataset

Then open demo/vellum/stoa/index.html (served from demo/vellum/, see README.md). Stdlib only.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = "swiss_dwellings"  # CC BY 4.0, floors with PDF + DXF + PNG and count and area questions
FLOOR = "site980_bldg2055_floor9178"  # Tudor 13:38: the example in both views
ENGLISH = ("How many ", "What is ")


def size_text(n):
    return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{round(n / 1e3)} kB"


def floor_questions(questions, floor):
    """The English questions about one floor of SOURCE (any of its files)."""
    mine = [q for q in questions if q["path"].split("/")[1:2] == [SOURCE]
            and Path(q["path"]).stem == floor and q["question"].startswith(ENGLISH)]
    if not mine:
        sys.exit(f"no English questions for {SOURCE}/{floor} in the dataset")
    return mine


def credit(source_dir):
    for line in (source_dir / "LICENSE.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("All files:"):
            return line.strip()
    sys.exit(f"no 'All files:' licence line in {source_dir / 'LICENSE.md'}")


KINDS = {".pdf": ("Vector PDF", "CAD"), ".dxf": ("DXF", "CAD"), ".png": ("PNG rendering", "Vision")}


def build(dataset, out, stem):
    questions = [json.loads(line) for line in (dataset / "questions.jsonl").open(encoding="utf-8") if line.strip()]
    mine = floor_questions(questions, stem)
    source_dir = dataset / "data" / SOURCE
    asked = {Path(q["path"]).name for q in mine}
    out.mkdir(exist_ok=True)
    files = []
    for f in sorted(source_dir.glob(stem + ".*")):
        if f.suffix not in KINDS:
            continue
        kind, lane = KINDS[f.suffix]
        entry = {"path": f.name, "size": size_text(f.stat().st_size), "kind": kind, "lane": lane,
                 "role": "source" if f.name in asked else "same"}
        if f.suffix == ".png":  # only the image is copied; the PDF and DXF are listed, not shipped
            shutil.copyfile(f, out / f.name)
            entry["image"] = f.name  # relative to stoa/index.html
        files.append(entry)
    if not any("image" in f for f in files):
        sys.exit(f"{stem} has no PNG to show")
    data = {
        "archive": stem,
        "source": SOURCE,
        "credit": credit(source_dir),
        "files": files,
        "questions": [{k: q[k] for k in ("question", "answer", "unit", "type")} for q in mine],
    }
    (out / "data.js").write_text("window.VStoaData = " + json.dumps(data, indent=1) + ";\n", encoding="utf-8")
    # stoa/index.html: the demo's page one folder down (no <base>: it would send the #/ links back to ../index.html)
    page = (HERE / "index.html").read_text(encoding="utf-8")
    page = re.sub(r'(src|href)="(?!https?:|#)', r'\1="../', page)
    page, n = re.subn(r'(<script src="\.\./data\.js"></script>)',
                      r'\1\n<script src="data.js"></script>\n<script src="../stoa.js"></script>', page, count=1)
    if not n:
        sys.exit("index.html changed shape: no data.js script to anchor on")
    shutil.copyfile(HERE / "vellum-logo.png", out / "vellum-logo.png")  # the header loads it relative to the page
    (out / "index.html").write_text(page, encoding="utf-8")
    return stem, len(mine)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=HERE.parents[1] / "data/stoa/full/junction-dataset",
                    help="the unzipped Stoa junction-dataset folder (default: the repo's data/stoa/full/...)")
    ap.add_argument("--floor", default=FLOOR, help=f"the {SOURCE} floor to show (default {FLOOR})")
    ap.add_argument("--out", type=Path, default=HERE / "stoa", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if not (a.dataset / "questions.jsonl").is_file():
        sys.exit(f"no questions.jsonl in {a.dataset}; pass --dataset (python3 tools/fetch_stoa_data.py full)")
    if not re.fullmatch(r"site\d+_bldg\d+_floor\d+", a.floor):  # it becomes a file name: no paths
        sys.exit(f"--floor must look like {FLOOR}")
    stem, n = build(a.dataset.expanduser(), a.out, a.floor)
    print(f"{stem}: {n} questions -> {a.out}/ (local only, never commit it). Open stoa/index.html.")


if __name__ == "__main__":
    main()
