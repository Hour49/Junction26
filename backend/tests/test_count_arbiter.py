"""The local count arbiter T1 (`arbiter-t1:<arm>`): the core's pick against local-dec's val picks,
the count swap it drives, L1's page input and probabilities, and the source in composition.

The parity fixture was recorded by scripts/check_arbiter_t1.py --fixture 6: T1's shipped model and
6 val units per family (pages renamed val-<n>, the changed picks first) with what the readers
read and T1's pick and P. The script itself checks all 2,389 val units."""

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app import composition
from app.adapters import count_arbiter
from app.adapters.count_arbiter import ArbiterCountExtractor, L1PageCounts, load_model
from app.composition import build_pipeline
from app.core.drawing.model import Element, Page, Plan, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.count_arbiter import ArbiterModel, FamilyModel, Reading, pick
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.settings import Settings

PARITY = Path(__file__).parent / "fixtures" / "count_arbiter" / "parity.json"
PNG = "data/cubicasa5k/x.png"
FILE = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(Page(page=1, width=40, height=30, unit="px"),))
PLAN = Plan(id="p1", page=1, box=(0.1, 0.1, 0.9, 0.9))


def png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "black").save(buffer, "PNG")
    return buffer.getvalue()


class Files:
    def read(self, path: str) -> bytes:
        assert path == PNG
        return png(20, 10)


class Read:
    """A reader with fixed elements: `counts` per class, scores descending from 0.9."""

    def __init__(self, counts: dict[str, int], read: tuple[Any, ...] | None = None) -> None:
        self.found = Extracted(
            method="detector", scale=Scale(status="no_scale"), plans=(PLAN,), read=read,
            elements=tuple(
                Element.model_validate({"id": f"{kind}{n}", "class": kind, "page": 1,
                                        "box": (0.2, 0.2, 0.3, 0.3),
                                        "attrs": {"score": round(0.9 - n / 100, 3)}})
                for kind, count in counts.items() for n in range(count)
            ),
        )  # fmt: skip

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.found


class Session:
    """onnxruntime's session for L1: fixed logits per head, keeps what it was fed."""

    def __init__(self, logits: list[list[float]]) -> None:
        self.logits = [np.array([row], np.float32) for row in logits]
        self.fed: dict[str, np.ndarray] = {}

    def get_inputs(self) -> list[Any]:
        return [type("Named", (), {"name": "page"})()]

    def get_outputs(self) -> list[Any]:
        return []

    def run(self, output_names: Any, input_feed: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.fed = input_feed
        return self.logits


HEADS = ("door", "window", "sink", "toilet", "shower+bathtub", "sauna", "plan")


def l1(top: dict[str, int] | None = None) -> L1PageCounts:
    """L1 sure of `top[head]` (else 0) for every head, 6 counts per head."""
    rows = [[10.0 if i == (top or {}).get(h, 0) else 0.0 for i in range(6)] for h in HEADS]
    return L1PageCounts(Session(rows), HEADS, 64, dict.fromkeys(HEADS, 1.0))


def follows_second(*families: str) -> ArbiterModel:
    """A model that picks the one-view count: only the feature `second == k` (index 12) counts."""
    coef = [0.0] * 19
    coef[12] = 5.0
    fit = FamilyModel((0.0,) * 19, (1.0,) * 19, tuple(coef), 0.0)
    return ArbiterModel(dict.fromkeys(families, fit), {f: {0: 0.5, 1: 0.5} for f in families})


def test_the_core_reproduces_t1s_val_picks() -> None:
    fixture = json.loads(PARITY.read_text())
    model = ArbiterModel(
        {f: FamilyModel(tuple(v["mu"]), tuple(v["sd"]), tuple(v["coef"]), v["intercept"])
         for f, v in fixture["arbiter"]["families"].items()},
        {f: {int(k): p for k, p in d.items()} for f, d in fixture["prior"].items()},
    )  # fmt: skip
    units = fixture["units"]
    assert sum(u["expected"] != u["base"] for u in units) >= 20  # changed picks are covered
    above = 0
    for u in units:
        reading = Reading(u["base"], tuple(u["scores"]), u["plans"], u["second"], u["probs"])
        got = pick(model, u["family"], reading)
        if u["base"] >= len(u["probs"]):  # T1 offline let L1 pull it down; the backend keeps it
            above += 1
            assert got.count == u["base"] != u["expected"]
            continue
        assert (u["page"], u["family"], got.count) == (u["page"], u["family"], u["expected"])
        assert got.p == pytest.approx(u["expected_p"], abs=1e-6)
    assert above == 1  # val-7's windows: base 42, T1 offline 25


def test_a_base_above_l1s_last_class_is_kept() -> None:
    """L1 has no class for a count above its last one, so it gives the base, base - 1 and base + 1
    the same floored P and its own top would win: val high_quality_architectural-10483, windows
    gold 41, base 42, picked 25 before. The base is kept there; inside L1's range it is not."""
    coef = [0.0] * 19
    coef[17] = 5.0  # a model that follows L1's top (feature `_top(probs) == k`)
    fit = FamilyModel((0.0,) * 19, (1.0,) * 19, tuple(coef), 0.0)
    model = ArbiterModel({"window": fit}, {"window": {25: 0.5}})
    probs = [0.0] * 25 + [0.6] + [0.4 / 15] * 15  # 0..40, top 25
    for base in (41, 42):
        got = pick(model, "window", Reading(base, (0.9,) * base, 1, base, probs))
        assert got.count == base
    assert pick(model, "window", Reading(40, (0.9,) * 40, 1, 40, probs)).count == 25


def test_the_pick_drops_the_lowest_scores_and_adds_unlocated_elements() -> None:
    base = Read({"shower": 3, "toilet": 1, "door": 4})
    second = Read({"shower": 2, "toilet": 2, "door": 1})
    arbiter = ArbiterCountExtractor(
        base, second, l1(), follows_second("shower+bathtub", "toilet"), Files()
    )
    found = arbiter.extract(FILE, SHEET)
    ids = [e.id for e in found.elements]
    assert [i for i in ids if i.startswith("shower")] == ["shower0", "shower1"]  # 0.88 dropped
    added = [e for e in found.elements if e.id.startswith("arbiter-")]
    assert [(e.class_, e.plan, e.box, e.attrs["located"]) for e in added] == [
        ("toilet", "p1", PLAN.box, False)
    ]
    assert sum(e.class_ == "door" for e in found.elements) == 4  # no fit for door: kept
    assert "shower+bathtub 3 -> 2" in found.notes[-1] and "toilet 1 -> 2" in found.notes[-1]


def test_a_family_a_reader_did_not_look_for_is_left_as_read() -> None:
    base = Read({"toilet": 1}, read=("door", "toilet"))
    second = Read({"toilet": 2}, read=("door",))
    found = ArbiterCountExtractor(base, second, l1(), follows_second("toilet"), Files()).extract(
        FILE, SHEET
    )
    assert found.elements == base.found.elements
    assert found.notes[-1] == "arbiter t1: counts kept"


def test_l1_reads_the_page_gray_top_left_on_white_and_softmaxes_with_its_temperature() -> None:
    session = Session([[0.0, float(np.log(3.0))], [0.0, 0.0]])
    model = L1PageCounts(session, ("door", "window"), 64, {"door": 1.0, "window": 2.0})
    probs = model.probs(png(20, 10))
    page = session.fed["page"]
    assert page.shape == (1, 1, 64, 64) and page.dtype == np.float32
    assert page[0, 0, :32, :].max() == 0.0  # the black page, long side 64, at the top left
    assert page[0, 0, 32:, :].min() == 1.0  # white below it
    assert probs["door"] == pytest.approx([0.25, 0.75])
    assert probs["window"] == pytest.approx([0.5, 0.5])


def write_model(folder: Path) -> None:
    fixture = json.loads(PARITY.read_text())
    folder.mkdir(parents=True)
    (folder / "arbiter.json").write_text(json.dumps(fixture["arbiter"]))
    (folder / "prior.json").write_text(json.dumps(fixture["prior"]))
    (folder / "l1.json").write_text(json.dumps({"heads": list(HEADS), "size": 64}))
    (folder / "temps.json").write_text(json.dumps(dict.fromkeys(HEADS, 1.0)))
    (folder / "l1.onnx").write_bytes(b"")


def test_load_model_refuses_a_prior_without_a_fitted_family(tmp_path: Path) -> None:
    write_model(tmp_path / "T1")
    assert set(load_model(tmp_path / "T1").families) == {*HEADS}
    (tmp_path / "T1" / "prior.json").write_text(json.dumps({"door": {"1": 1.0}}))
    with pytest.raises(InvalidInputError, match=r"prior\.json has no family"):
        load_model(tmp_path / "T1")


def test_the_source_arbiter_t1_runs_eight_views_one_view_and_l1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = []

    def from_folder(files: object, folder: Path, thresholds: Path | None = None, views: int = 1):
        seen.append((folder.name, thresholds and thresholds.name, views))
        return Read({})

    write_model(tmp_path / "models" / "arbiter")
    monkeypatch.setattr(composition.OnnxDetector, "from_folder", from_folder)
    monkeypatch.setattr(count_arbiter, "onnx_session", lambda path: Session([]))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("ARBITER_MODEL_DIR", str(tmp_path / "models" / "arbiter"))
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=arbiter-t1:C:C-onnx-val,plans=one-plan")
    build_pipeline(Settings(), tmp_path)
    assert seen == [("C", None, 8), ("C", "C-onnx-val.thresholds.json", 1)]
