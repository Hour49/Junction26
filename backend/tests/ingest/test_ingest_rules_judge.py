"""TRIAGE_JUDGE=rules (decision 0010, triage-models.md section 3): the baseline relevance judge,
the file's class alone, no model. Its `why` says it is a rule on the kind of picture, not a
reading of what the picture shows."""

from pathlib import Path

import pytest
from conftest import MakeService
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped
from triage_fakes import FakeClassifier, FakeDescriber

from app.adapters.triage.rules_judge import JUDGE, RulesJudge
from app.composition import _triage  # pyright: ignore[reportPrivateUsage]
from app.core.ingest.model import Description, ProjectContext, Unavailable
from app.core.ingest.triage import TriageSteps
from app.settings import Settings

SAID = Description(text="A picture.", subject="a picture", model="fake describer")
CONTEXT = ProjectContext(plans=("d1",), plan_text=(), file_names=(), descriptions=())


def test_not_a_drawing_is_unrelated_and_another_drawing_related_by_rule_without_reading() -> None:
    unrelated = RulesJudge().judge("not_drawing", SAID, CONTEXT)
    related = RulesJudge().judge("other_drawing", SAID, CONTEXT)
    assert not isinstance(unrelated, Unavailable) and not isinstance(related, Unavailable)
    assert (unrelated.verdict, related.verdict) == ("unrelated", "related")
    for found in (unrelated, related):
        assert found.judge == JUDGE == "rule on the kind of picture, no model"
        assert "without reading what they show" in found.why
        assert (found.matched_on, found.plans) == ((), ())
    assert unrelated.why.startswith("A picture that is not a drawing;")
    assert isinstance(RulesJudge().judge("floor_plan", SAID, CONTEXT), Unavailable)


def test_in_ingest_each_described_non_plan_gets_the_rule_verdict(make_service: MakeService) -> None:
    classifier = FakeClassifier({SCAN: "other_drawing", PHOTO: "not_drawing"})
    describer = FakeDescriber({SCAN: ("an elevation", ()), PHOTO: ("a cat", ())})
    steps = TriageSteps(classifier=classifier, describer=describer, judge=RulesJudge(), name="t")
    ingest = make_service(triage=steps)
    files = {"plan.pdf": PLAN, "elevation.png": SCAN, "cat.jpg": PHOTO}
    status = ingest.wait(ingest.start("site.zip", zipped(files)))
    elevation, cat = file_of(status, "elevation.png").triage, file_of(status, "cat.jpg").triage
    assert elevation is not None and cat is not None
    assert (elevation.verdict, cat.verdict) == ("related", "unrelated")
    assert cat.relevance is not None and cat.relevance.judge == JUDGE
    assert (elevation.note, cat.note) == (None, None)


def test_the_setting_wires_the_rules_judge_and_off_wires_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the settings
    on = _triage(Settings(triage_classifier="rules", triage_judge="rules"))
    assert on is not None and isinstance(on.judge, RulesJudge)
    assert on.name == "classifier=rules, describer=off, judge=rules"
    off = _triage(Settings(triage_classifier="rules"))
    assert off is not None and off.judge is None
