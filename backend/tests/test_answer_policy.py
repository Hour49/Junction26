"""ANSWER_POLICY: the file that sends (source, family) pairs to the prior, and its wiring."""

import json
from pathlib import Path

import pytest

from app.adapters.answer_policy import load_policy
from app.composition import build_pipeline
from app.core.errors import InvalidInputError
from app.settings import Settings


def write(tmp_path: Path, doc: object) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def policy(**families: str) -> dict[str, object]:
    """An answer_policy_v1 file as golden's leaderboard writes it (extra fields trimmed)."""
    return {
        "schema": "answer_policy_v1",
        "part": "val",
        "families": {
            family: {"source": source, "arm": None if source == "prior" else source[14:]}
            for family, source in families.items()
        },
    }


def test_only_families_whose_pick_is_the_prior_go_to_the_prior(tmp_path: Path) -> None:
    doc = policy(
        **{"room:kitchen": "prior", "room:wc": "data/stoa/exp/ocr/G4", "shower+bathtub": "prior"}
    )
    assert load_policy(write(tmp_path, doc)) == frozenset(
        {("cubicasa5k", "room:kitchen"), ("cubicasa5k", "shower+bathtub")}
    )


@pytest.mark.parametrize(
    "doc",
    [
        {"cubicasa5k": {"room:kitchen": "prior"}},  # the old {source: {family: choice}} shape
        {**policy(door="prior"), "schema": "answer_policy_v2"},
        {**policy(door="prior"), "part": "golden"},  # never a policy tuned on golden
        {**policy(), "families": ["door"]},
        {**policy(), "families": {"door": "prior"}},
        {**policy(), "families": {"door": {"arm": None}}},
    ],
)
def test_a_malformed_policy_is_refused(tmp_path: Path, doc: object) -> None:
    with pytest.raises(InvalidInputError):
        load_policy(write(tmp_path, doc))


def test_the_setting_names_the_file_and_empty_means_none(tmp_path: Path) -> None:
    path = write(tmp_path, policy(**{"room:bathroom": "prior"}))
    with_policy = build_pipeline(Settings(answer_policy=str(path)), tmp_path)
    assert with_policy.prior_families == frozenset({("cubicasa5k", "room:bathroom")})
    assert build_pipeline(Settings(answer_policy=""), tmp_path).prior_families == frozenset()
