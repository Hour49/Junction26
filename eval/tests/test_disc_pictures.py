"""The discipline-picture bench scorer (spec docs/specs/backend/discipline-pictures.md, P4):
hand-made truth files and fake reader fact sheets; metrics as AC-16 and AC-18."""

import json
from pathlib import Path

import pytest

from stoa_eval.cli import main
from stoa_eval.disc_pictures import (
    NONE_SYSTEM,
    DiscPred,
    DiscTruth,
    aggregates,
    bars,
    pick_split,
    score,
    truth_from_render,
    wilson_lower,
)


def truth(picture: str = "p1", **changes: object) -> DiscTruth:
    body: dict[str, object] = {
        "picture": picture, "building": "b1", "discipline": "heating", "storey": "2",
        "dpi": 150, "degradation": "clean", "legend": True, "scale": True,
        "width_px": 1000, "height_px": 1000,
        "symbols": [
            {"label": "A", "kind": "space_heater", "points": [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]},
            {"label": "B", "kind": "space_heater", "points": [[0.2, 0.2], [0.3, 0.3]]},
            {"label": "C", "kind": "valve", "points": [[0.7, 0.7]]},
        ],
        "runs": [
            {"kind": "pipe_segment", "system": "heating", "size": None, "length_m": 40.0},
            {"kind": "pipe_segment", "system": "heating", "size": "DN20", "length_m": 10.0},
            {"kind": "pipe_segment", "system": "heating", "size": "DN15", "length_m": 5.0},
        ],
    }  # fmt: skip
    body.update(changes)
    return DiscTruth.model_validate(body)


def spot(x: float, y: float) -> dict[str, object]:
    return {"page": 1, "box": [x - 0.001, y - 0.001, x + 0.001, y + 0.001], "reader": "vlm"}


def fact(topic: str, subject: str, value: float, **changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "topic": topic, "subject": subject, "value": value, "unit": "count",
        "discipline": "heating", "source": "picture:vlm+template",
    }  # fmt: skip
    body.update(changes)
    return body


def pred(picture: str = "p1", facts: list[dict[str, object]] | None = None, **changes: object):
    body: dict[str, object] = {
        "picture": picture,
        "sheet": {"model": picture, "disciplines": ["heating"], "facts": facts or []},
        "agreed": {},
        "cost_usd": 0.01,
        "seconds": 2.0,
    }
    body.update(changes)
    return DiscPred.model_validate(body)


def sample_pred() -> DiscPred:
    facts = [
        fact("space_heater.count", "all", 6),  # the kind total is not a label unit
        fact("space_heater.count", "A", 3,
             spots=[spot(0.101, 0.1), spot(0.5, 0.52), spot(0.3001, 0.3)]),
        fact("space_heater.count", "B", 3),
        fact("pipe_segment.length", "all", 41.0, unit="m", system="heating"),
        fact("pipe_segment.size_length", "DN20", 10.8, unit="m", system="heating"),
    ]  # fmt: skip
    return pred(facts=facts, agreed={"A": True, "B": False})


def test_counts_exact_within_one_and_refused() -> None:
    report = score([truth()], [sample_pred()])
    m = report.overall
    assert (m.counts, m.count_exact, m.count_within_1, m.count_refused) == (3, 1, 2, 1)


def test_agreed_units_and_their_exact_share() -> None:
    m = score([truth()], [sample_pred()]).overall
    assert (m.agreed, m.agreed_exact) == (1, 1)
    assert m.agreed_lower == pytest.approx(wilson_lower(1, 1))


def test_wilson_lower_bound() -> None:
    assert wilson_lower(9, 10) == pytest.approx(0.5958, abs=1e-4)
    assert wilson_lower(0, 0) == 0.0


def test_symbol_recall_precision_one_to_one_within_near() -> None:
    # A: (0.101, 0.1) is 1 px from (0.1, 0.1); (0.5, 0.52) is 20 px off; the third is no A point.
    # B, C have no spots. near 0.006 of a 1414 px diagonal is 8.5 px.
    m = score([truth()], [sample_pred()]).overall
    assert (m.truth_points, m.pred_spots, m.spot_hits) == (6, 3, 1)


def test_one_truth_point_matches_one_spot_only() -> None:
    facts = [fact("space_heater.count", "C", 2, spots=[spot(0.7, 0.7), spot(0.7005, 0.7)])]
    m = score([truth()], [pred(facts=facts)]).overall
    assert (m.pred_spots, m.spot_hits) == (2, 1)


def test_near_scales_with_page_aspect() -> None:
    # 2000 x 500 px: diagonal 2062 px, near = 12.4 px; 0.005 of the width is 10 px (in),
    # 0.01 of the width is 20 px (out).
    points = [[0.5, 0.5], [0.2, 0.2]]
    wide = truth(
        width_px=2000, height_px=500, symbols=[{"label": "C", "kind": "valve", "points": points}]
    )
    facts = [fact("valve.count", "C", 2, spots=[spot(0.505, 0.5), spot(0.21, 0.2)])]
    assert score([wide], [pred(facts=facts)]).overall.spot_hits == 1


def test_lengths_within_5_and_10_percent_and_refused() -> None:
    m = score([truth()], [sample_pred()]).overall
    assert (m.runs, m.run_within_5, m.run_within_10, m.run_refused) == (3, 1, 2, 1)


def test_refusals_cover_counts_and_runs() -> None:
    m = score([truth()], [sample_pred()]).overall
    assert m.refused_share == pytest.approx(2 / 6)


def test_picture_without_a_pred_refuses_everything() -> None:
    m = score([truth()], []).overall
    assert (m.count_refused, m.run_refused, m.pages) == (3, 3, 0)


def test_unknown_pred_picture_is_an_error() -> None:
    with pytest.raises(ValueError, match="no truth"):
        score([truth()], [pred("zz")])


def test_groups_by_discipline_and_variant() -> None:
    outlet = {"label": "S", "kind": "outlet", "points": [[0.5, 0.5]]}
    t2 = truth(
        "p2", discipline="electrical", degradation="scan", dpi=100, symbols=[outlet], runs=[]
    )
    report = score([truth(), t2], [sample_pred()])
    assert set(report.by_discipline) == {"heating", "electrical"}
    assert set(report.by_variant) == {"150dpi-clean", "100dpi-scan"}
    assert report.by_discipline["electrical"].count_refused == 1
    no_legend = truth("p3", legend=False, scale=False)
    assert score([no_legend], []).by_variant.keys() == {"150dpi-clean-no-legend-no-scale"}


def test_cost_median_p95_and_over_budget() -> None:
    truths = [truth(f"p{i}") for i in range(20)]
    preds = [pred(f"p{i}", cost_usd=0.01 * (i + 1), seconds=float(i)) for i in range(20)]
    m = score(truths, preds).overall
    assert m.cost_median == pytest.approx(0.105)
    assert m.cost_p95 == pytest.approx(0.19)  # nearest rank: the 19th of 20
    assert m.over_budget == 5  # 0.16 .. 0.20 > 0.15
    assert m.seconds_median == pytest.approx(9.5)


def test_pick_split_by_building() -> None:
    truths = [truth("p1", building="b1"), truth("p2", building="b2"), truth("p3", building="b3")]
    manifest = {"dev": ["b1", "b3"], "test": ["b2"]}
    assert [t.picture for t in pick_split(truths, manifest, "dev")] == ["p1", "p3"]
    assert [t.picture for t in pick_split(truths, manifest, "test")] == ["p2"]
    with pytest.raises(ValueError, match="both"):
        pick_split(truths, {"dev": ["b1"], "test": ["b1"]}, "dev")


def _gate_case(n: int, exact: int) -> tuple[list[DiscTruth], list[DiscPred]]:
    """n pictures, one agreed label each (exact on the first `exact`), one 10 m run each."""
    truths, preds = [], []
    for i in range(n):
        heater = {"label": "A", "kind": "space_heater", "points": [[0.5, 0.5]]}
        run = {"kind": "pipe_segment", "system": "h", "size": None, "length_m": 10.0}
        degradation = "clean" if i % 2 else "scan"
        truths.append(truth(f"p{i}", degradation=degradation, symbols=[heater], runs=[run]))
        facts = [
            fact("space_heater.count", "A", 1 if i < exact else 2, spots=[spot(0.5, 0.5)]),
            fact("pipe_segment.length", "all", 10.5, unit="m", system="h"),
        ]
        preds.append(pred(f"p{i}", facts=facts, agreed={"A": True}, cost_usd=0.03))
    # a 200 dpi picture is outside the AC-16 subset and must not count
    truths.append(truth("x", dpi=200))
    preds.append(pred("x", cost_usd=0.03))
    return truths, preds


def test_bars_pass_on_enough_exact_agreed_units() -> None:
    result = bars(score(*_gate_case(70, 70)))
    assert result["ac16"]["units"] == 70
    assert all(result["ac16"]["pass"].values())
    assert all(result["ac18"]["pass"].values())


def test_bars_fail_below_60_units_or_low_bound() -> None:
    few = bars(score(*_gate_case(50, 50)))["ac16"]["pass"]
    assert not few["units"]
    assert few["exact"]
    low = bars(score(*_gate_case(70, 62)))["ac16"]["pass"]  # 88.6%
    assert not low["exact"]
    assert not low["lower"]


def test_aggregates_name_no_picture_label_or_building() -> None:
    text = json.dumps(aggregates(score([truth("secretstem", building="bldg")], [])))
    for word in ("secretstem", "bldg", '"A"', "DN20"):
        assert word not in text


def render_body(picture: str = "p1", building: str = "b1") -> dict[str, object]:
    """A truth file as the renderer writes it (plan_picture.py): the model's name, the page size,
    one symbol per instance in pixels, runs per (system, size) without a kind, and a run without
    a printed size only in its system's total."""
    t = truth(picture)
    return {
        "picture": picture, "model": building, "discipline": "heating", "storey": "2",
        "dpi": 150, "variant": "clean", "ratio": 50, "size_px": [1000, 1000],
        "legend": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
        "symbols": [
            {"label": s.label, "kind": s.kind, "x": x * 1000, "y": y * 1000}
            for s in t.symbols for x, y in s.points
        ],
        "counts": {s.label: len(s.points) for s in t.symbols},
        "runs": [{"system": "heating", "size": size, "length_m": m, "plan_m": m / 2}
                 for size, m in (("DN20", 10.0), ("DN15", 5.0), (None, 25.0))],
        "system_lengths_m": {"heating": 40.0},
    }  # fmt: skip


RUNS = [
    {"kind": None, "system": "heating", "size": None, "length_m": 40.0},
    {"kind": None, "system": "heating", "size": "DN20", "length_m": 10.0},
    {"kind": None, "system": "heating", "size": "DN15", "length_m": 5.0},
]


def test_truth_from_render_reads_the_renderers_file() -> None:
    assert truth_from_render(render_body()) == truth(runs=RUNS)


def test_truth_from_render_runs_without_a_system_as_printed() -> None:
    body = render_body()
    body["runs"] = [{"system": None, "size": "27 mmø", "length_m": 2.0, "plan_m": 1.0},
                    {"system": None, "size": None, "length_m": 3.0, "plan_m": 1.0}]  # fmt: skip
    body["system_lengths_m"] = {}  # the renderer totals named systems only
    runs = {(r.system, r.size): r.length_m for r in truth_from_render(body).runs}
    assert runs == {(NONE_SYSTEM, None): 5.0, (NONE_SYSTEM, "27 mmø"): 2.0}


def test_truth_from_render_flags_come_from_the_variant() -> None:
    no_legend = truth_from_render(render_body() | {"variant": "no-legend", "legend": []})
    assert no_legend.variant == "150dpi-clean-no-legend"
    no_scale = truth_from_render(render_body() | {"variant": "no-scale", "ratio": None})
    assert no_scale.variant == "150dpi-clean-no-scale"
    no_symbols = truth_from_render(render_body() | {"variant": "photo", "legend": []})
    assert no_symbols.variant == "150dpi-photo"  # an empty legend is a page without symbols


def test_truth_from_render_names_missing_fields() -> None:
    body = render_body()
    del body["model"]
    body["symbols"] = [{"kind": "valve", "x": 1, "y": 1}]
    with pytest.raises(ValueError, match="model, label"):
        truth_from_render(body)


def test_truth_from_render_system_total_without_runs() -> None:
    body = render_body() | {"system_lengths_m": {"heating": 40.0, "cooling": 3.0}}
    with pytest.raises(ValueError, match=r"cooling.*no runs"):
        truth_from_render(body)


def test_a_run_without_a_kind_matches_any_kinds_length() -> None:
    facts = [fact("duct_segment.length", "all", 39.0, unit="m", system="heating"),
             fact("symbol.size_length", "DN20", 10.0, unit="m", system="heating")]  # fmt: skip
    m = score([truth(runs=RUNS)], [pred(facts=facts)]).overall
    assert (m.runs, m.run_within_5, m.run_refused) == (3, 2, 1)


def _write_bench(root: Path) -> tuple[Path, Path]:
    bench = root / "bench"
    (bench / "b1").mkdir(parents=True)
    (bench / "b1" / "p1.json").write_text(json.dumps(render_body()), "utf-8")
    (bench / "b2").mkdir()
    (bench / "b2" / "p2.json").write_text(json.dumps(render_body("p2", "b2")), "utf-8")
    (bench / "manifest.json").write_text(json.dumps({"dev": ["b1"], "test": ["b2"]}))
    preds = root / "preds.jsonl"
    preds.write_text(sample_pred().model_dump_json() + "\n", "utf-8")
    return bench, preds


def test_cli_scores_dev_and_records_aggregates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bench, preds = _write_bench(tmp_path)
    results = tmp_path / "runs"
    argv = ["disc-pictures", str(bench), str(preds), "--name", "fake reader", "--results",
            str(results)]  # fmt: skip
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "count exact" in out
    (record,) = results.glob("*.json")
    body = json.loads(record.read_text("utf-8"))
    assert body["split"] == "dev"
    assert body["report"]["overall"]["counts"] == 3  # p2 (test) left out
    assert "p1" not in record.read_text("utf-8")


def test_cli_test_split_needs_milestone(tmp_path: Path) -> None:
    bench, preds = _write_bench(tmp_path)
    assert main(["disc-pictures", str(bench), str(preds), "--split", "test"]) == 1
    argv = ["disc-pictures", str(bench), str(preds), "--split", "test", "--milestone"]
    assert main(argv) == 0
