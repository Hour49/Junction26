"""list_drawings with files set aside (live S1 2026-11-15): the chat's step line counts them and
the model reads each one's reason."""

import json

from app.core.agent.loop import _for_model, _summary

LISTED = {
    "items": [{"drawing_id": "0123456789abcdef", "name": "plan.pdf"}],
    "set_aside": [{"path": "site/plan.dwg", "reason": "export it as a PDF and upload that"}],
}


def test_the_step_line_counts_the_drawings_and_the_files_set_aside() -> None:
    assert _summary("list_drawings", LISTED, {}) == "1 drawing, 1 set aside"
    assert _summary("list_drawings", LISTED["items"], {}) == "1 drawing"


def test_the_model_reads_each_file_set_aside_with_its_reason() -> None:
    assert json.loads(_for_model(LISTED))["set_aside"] == LISTED["set_aside"]
