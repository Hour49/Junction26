"""L1 of .agents/exp/user-scale.md: on dev CubiCasa gold sheets with a gold scale, giving one room's
area (as the gold scale gives it) answers every other room within 2% of the gold scale's area.
Info: the same with the room's gold `area_m2`. 0 USD, gold files only, split dev only.
Run from backend/: uv run python ../prototypes/user-scale/l1.py"""

import json
import statistics
from pathlib import Path

from app.core.drawing.model import Drawing, Scale
from app.core.pipeline.raster_scale import _shoelace, rooms_with_areas  # pyright: ignore
from app.core.pipeline.user_scale import Given, user_scale, with_user_scale

ROOT = Path("../data/stoa/golden/v2/part1_extraction")
dev = {
    json.loads(line)["file"]
    for line in (ROOT / "files.jsonl").read_text().splitlines()
    if json.loads(line)["split"] == "dev" and json.loads(line)["source"] == "cubicasa5k"
}
sheets = triples = inside = 0
info: list[float] = []
worst: list[tuple[float, str, str, str]] = []
for path in sorted((ROOT / "gold" / "cubicasa5k").glob("*.json")):
    body = json.loads(path.read_text())
    if body["file"] not in dev:
        continue
    for key in ("schema", "split", "truth", "counts"):
        body.pop(key, None)
    gold = Drawing.model_validate(body)
    s = gold.scale.reference_m_per_unit or gold.scale.m_per_unit
    rooms = [r for r in gold.rooms if r.polygon]
    if s is None or len(rooms) < 2:
        continue
    sheets += 1
    page = gold.pages[0]
    bare = [r.model_copy(update={"area_m2": None, "area_status": None, "area_source": None,
                                 "area_uncertainty": None}) for r in gold.rooms]  # fmt: skip
    plain = gold.model_copy(update={"scale": Scale(status="no_scale"), "rooms": tuple(bare)})
    at_gold, _ = rooms_with_areas(bare, Scale(status="scaled", m_per_unit=s), gold.pages)
    want = {r.id: r.area_m2 for r in at_gold}
    for k in rooms:
        exact = _shoelace(k.polygon) * page.width * page.height * s**2  # pyright: ignore
        for value, record in ((exact, True), (k.area_m2, False)):
            if value is None or value <= 0:
                continue
            given = Given(kind="area", value=value, room=k.label or k.type, text="x")
            scale = user_scale(plain, given, next(r for r in bare if r.id == k.id), None)
            assert isinstance(scale, Scale), scale
            got = {r.id: r.area_m2 for r in with_user_scale(plain, scale).rooms}
            for r in rooms:
                if r.id == k.id or not want.get(r.id):
                    continue
                off = abs(got[r.id] / want[r.id] - 1)  # pyright: ignore
                if record:
                    triples += 1
                    inside += off <= 0.02
                    worst.append((off, path.stem, k.id, r.id))
                else:
                    info.append(off)
worst.sort(reverse=True)
print(f"L1 sheets {sheets} triples {triples} within 2%: {inside} ({inside / triples:.2%})")
print("worst 5:", [(f"{o:.3%}", *rest) for o, *rest in worst[:5]])
n = len(info)
print(f"info (given = gold area_m2): {n} triples, within 2% {sum(o <= 0.02 for o in info) / n:.1%}, "
      f"within 10% {sum(o <= 0.10 for o in info) / n:.1%}, median {statistics.median(info):.1%}")
