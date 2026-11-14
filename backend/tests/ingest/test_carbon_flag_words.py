"""The Carbon reading flags in plain words (brief r8 BS), and a reading stored with the old words
still read as Carbon's: a stored Outcome is reused by content across code versions."""

from app.core.ingest.judge import CARBON_FLAG, CARBON_PART_FLAG, reading_flags
from app.core.ingest.model import Outcome

OLD = "counted by Gemini Carbon: its counts are not measured yet"
OLD_PART = "read in part by Gemini Carbon: its counts are not measured yet"


def test_the_flags_say_what_carbon_did_without_jargon() -> None:
    for flag in (CARBON_FLAG, CARBON_PART_FLAG):
        assert "not measured" not in flag and "check its marks" in flag
    assert reading_flags("png_plan", None, carbon="elements") == (CARBON_FLAG,)


def test_a_reading_stored_with_the_old_words_is_read_in_todays() -> None:
    stored = {
        "key": "d1",
        "project_id": "p1",
        "path": "plan.png",
        "state": "flagged",
        "reason": f"a scanned PDF, read as an image; {OLD} (12 elements)",
        "flags": ["a scanned PDF, read as an image", OLD],
    }
    outcome = Outcome.model_validate(stored)
    assert outcome.flags == ("a scanned PDF, read as an image", CARBON_FLAG)
    assert outcome.reason == f"a scanned PDF, read as an image; {CARBON_FLAG} (12 elements)"
    part = Outcome.model_validate(stored | {"flags": [OLD_PART], "reason": OLD_PART})
    assert part.flags == (CARBON_PART_FLAG,) and part.reason == CARBON_PART_FLAG
    again = Outcome.model_validate(outcome.model_dump(mode="json"))
    assert again == outcome
