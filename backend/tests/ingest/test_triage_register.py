"""Decision 0010 section 8: the sheet register on an image file, the triage class derived from
it, and relevance by rule over the description's form."""

from typing import Any

import pytest
from conftest import MakeService
from pydantic import ValidationError
from test_ingest_triage import PHOTO, PLAN, SCAN, file_of, zipped
from triage_fakes import FakeClassifier, FakeDescriber, steps

from app.adapters.triage.rules_judge import RulesJudge
from app.core.ingest.model import (
    Classified,
    Description,
    ProjectContext,
    Register,
    SheetKind,
    TriageClass,
    Unavailable,
    class_of,
)
from app.core.ingest.triage import RULE, relevance_by_rule, relevance_of, words_of


def register(kind: SheetKind, has_floor_plan: bool = False) -> Register:
    return Register(
        kind=kind,
        has_floor_plan=has_floor_plan,
        photo_of_sheet=False,
        scale_shown="bar",
        quality="good",
        method="fake classifier",
    )


def said(visible: str = "", building: bool = False, seen: tuple[str, ...] = ()) -> Description:
    return Description(
        text="A picture.",
        subject="a picture",
        text_seen=seen,
        model="fake describer",
        what_it_is="other",
        shows_building=building,
        visible_text=visible,
        detail="A picture, at length.",
    )


def context(**fields: Any) -> ProjectContext:
    found: dict[str, Any] = {
        "plans": ("d1",),
        "project_name": "villa-rosa.zip",
        "plan_text": ("Küche", "Bad", "Wohnen"),
        "file_names": ("plans/ground.pdf", "photos/organ-score.png"),
        "descriptions": (),
    }
    return ProjectContext(**(found | fields))


@pytest.mark.parametrize(
    ("kind", "has_floor_plan", "expected"),
    [
        ("floor_plan", True, "floor_plan"),
        ("floor_plan", False, "floor_plan"),  # the kind says plan: unsure means plan
        ("photograph", True, "floor_plan"),  # a photo of a plan
        ("multi_view_sheet", True, "floor_plan"),
        ("multi_view_sheet", False, "other_drawing"),
        ("elevation", False, "other_drawing"),
        ("site_plan_or_map", False, "other_drawing"),
        ("engineering_non_building", False, "other_drawing"),
        ("photograph", False, "not_drawing"),
        ("not_architecture", False, "not_drawing"),
        ("cover_or_text_sheet", False, "not_drawing"),
        ("other", False, "not_drawing"),
    ],
)
def test_the_class_is_derived_from_the_register(
    kind: SheetKind, has_floor_plan: bool, expected: TriageClass
) -> None:
    assert class_of(register(kind, has_floor_plan)) == expected
    given = Classified.model_validate(
        {"p_plan": 0.5, "method": "m", "register": register(kind, has_floor_plan)}
    )
    assert given.class_ == expected


def test_a_class_that_disagrees_with_the_register_is_refused() -> None:
    with pytest.raises(ValidationError, match="disagrees with the register"):
        Classified.model_validate(
            {"class": "floor_plan", "p_plan": 0.1, "method": "m", "register": register("section")}
        )


def test_an_image_gets_the_register_its_classifier_reads_and_other_files_none(
    make_service: MakeService,
) -> None:
    classifier = FakeClassifier({PHOTO: "not_drawing"}, registers={SCAN: register("elevation")})
    ingest = make_service(triage=steps(classifier))
    files = {"plan.pdf": PLAN, "elevation.png": SCAN, "cat.jpg": PHOTO}
    status = ingest.wait(ingest.start("site.zip", zipped(files)))
    elevation = file_of(status, "elevation.png")
    assert elevation.triage is not None and elevation.triage.register_ == register("elevation")
    assert elevation.triage.class_ == "other_drawing" and elevation.state == "set_aside"
    shown = elevation.model_dump(mode="json")["triage"]
    assert (shown["class"], shown["register"]["kind"]) == ("other_drawing", "elevation")
    # a vector PDF is not triaged; a classifier that reads no register gives none
    plan, cat = file_of(status, "plan.pdf"), file_of(status, "cat.jpg")
    assert plan.triage is None and cat.triage is not None and cat.triage.register_ is None


def test_a_floor_plan_keeps_its_register_too(make_service: MakeService) -> None:
    plan = register("floor_plan", True).model_copy(update={"scale_shown": "ratio_text"})
    ingest = make_service(triage=steps(FakeClassifier({}, registers={SCAN: plan})))
    status = ingest.wait(ingest.start("site.zip", zipped({"scan.png": SCAN})))
    scan = file_of(status, "scan.png")
    assert scan.triage is not None and scan.triage.register_ == plan
    assert scan.triage.class_ == "floor_plan" and scan.state != "set_aside"


def test_a_shared_word_makes_it_related_and_the_why_names_it_and_where() -> None:
    found = relevance_by_rule(said("VILLA ROSA\nKüche 12 m²"), context())
    assert found.verdict == "related"
    assert found.matched_on == ("'kuche' (plan text)", "'rosa' (name)", "'villa' (name)")
    assert found.why == (
        "Related: 'kuche', 'rosa', 'villa', printed on it, are in the project's name and plan "
        "text; it shows no building."
    )
    assert found.judge == RULE


def test_a_building_with_no_match_is_unsure_and_with_a_match_related() -> None:
    alone = relevance_by_rule(said("Allegro", building=True), context())
    assert (alone.verdict, alone.matched_on) == ("unsure", ())
    assert alone.why == (
        "Unsure: it shows a building, but none of its printed words is in the project's name, "
        "file and folder names or plan text."
    )
    blank = relevance_by_rule(said(building=True), context())
    assert blank.why == "Unsure: it shows a building, but it has no printed text."
    both = relevance_by_rule(said("Wohnen", building=True), context())
    assert (both.verdict, both.matched_on) == ("related", ("'wohnen' (plan text)",))
    assert both.why == (
        "Related: 'wohnen', printed on it, is in the project's plan text; it shows a building."
    )


def test_no_building_and_no_shared_word_is_unrelated_and_says_why() -> None:
    printed = relevance_by_rule(said("Allegro ma non troppo"), context())
    assert (printed.verdict, printed.matched_on) == ("unrelated", ())
    assert printed.why == (
        "Unrelated: it shows no building, and none of its printed words is in the project's "
        "name, file and folder names or plan text."
    )
    blank = relevance_by_rule(said(), context())
    assert blank.why == "Unrelated: it shows no building, and it has no printed text."


def test_numbers_drawing_words_and_short_words_never_match() -> None:
    files = ("2024/plan-1-100.pdf", "a/bad.png")
    found = relevance_by_rule(said("PLAN 1:100 2024 Bad"), context(file_names=files))
    assert found.verdict == "unrelated"
    assert words_of(("Grundriß 1:50, Maßstab; Façade Ölberg",)) == {"olberg"}


def test_text_seen_counts_as_printed_words() -> None:
    found = relevance_by_rule(said(seen=("Wohnen",)), context())
    assert found.verdict == "related"


def test_the_file_s_own_name_is_not_a_fact_about_the_project() -> None:
    """A score named organ-score.png with "Organ" printed on it must not match itself."""
    found = relevance_of(
        RulesJudge(), "not_drawing", said("ORGAN SCORE"), context(), "photos/organ-score.png"
    )
    assert not isinstance(found, Unavailable) and found.verdict == "unrelated"
    other = relevance_of(RulesJudge(), "not_drawing", said("ORGAN"), context(), "x/other.png")
    assert not isinstance(other, Unavailable)
    assert other.verdict == "related"  # the score's name is a fact about the other file


def test_the_rules_judge_reads_the_project_name_from_ingest(make_service: MakeService) -> None:
    classifier = FakeClassifier({SCAN: "other_drawing"})
    describer = FakeDescriber({SCAN: ("a title sheet", ("HAUS SONNE",))})
    ingest = make_service(triage=steps(classifier, describer, RulesJudge()))
    files = {"plan.pdf": PLAN, "scan.png": SCAN}
    status = ingest.wait(ingest.start("haus-sonne.zip", zipped(files)))
    scan = file_of(status, "scan.png").triage
    assert scan is not None and scan.relevance is not None
    assert scan.relevance.matched_on == ("'haus' (name)", "'sonne' (name)")
