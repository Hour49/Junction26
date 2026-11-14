"""A judge reads these (Tudor's chat QA, board #14 c6882199550): a refusal says what was read,
what wasn't and what the user can do, without "yet" or "not supported" that sound like a missing
feature, and claims nothing new."""

from test_review_core import photo

from app.adapters.archive.probe import FileProbe
from app.adapters.question_templates import TemplateParser
from app.api.project_ask import LACKS
from app.core.answering.answer import PRIOR_BY_POLICY
from app.core.answering.model import Query, Unsupported
from app.core.review.ask import TEXTS, _refusal  # pyright: ignore[reportPrivateUsage]

SOUNDS_UNBUILT = ("yet", "not supported", "not built")


def test_no_refusal_text_sounds_like_a_missing_feature() -> None:
    for words in (*TEXTS.values(), *(said for pair in LACKS.values() for said in pair)):
        assert not any(phrase in words for phrase in SOUNDS_UNBUILT), words


def test_a_sheet_this_setup_has_no_reader_for_says_so_and_what_still_works() -> None:
    assert TEXTS["no-reader-yet"] == (
        "This sheet wasn't read, so nothing on it was counted or measured: this setup has no "
        "reader for this kind of sheet. You can still ask about the project's other drawings."
    )
    assert LACKS["no-reader"] == (
        "gives no reliable number for it",
        "give no reliable number for it",
    )


def test_a_family_the_policy_answers_from_the_prior_says_why() -> None:
    query = Query(measure="count", subject="door")
    code, words = _refusal(PRIOR_BY_POLICY, query, query.key(), photo())
    assert (code, words) == (
        "no-reader",
        "On sheets like this one, our reader got this kind of question wrong too often when we "
        "measured it, so no number is given.",
    )


def test_a_schedule_question_that_is_no_lookup_says_so_plainly() -> None:
    parsed = TemplateParser().parse("Which items are listed in the legend?")
    assert parsed == Unsupported(reason="a schedule question that can't be turned into one lookup")


def test_a_dwg_file_says_what_to_upload_instead() -> None:
    found = FileProbe().probe(b"AC1032" + bytes(200))
    assert (
        found.did
        == "a DWG drawing: DWG files can't be opened here; export it as a PDF and upload that"
    )
