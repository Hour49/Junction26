"""answer_v1 lines on disk (the `AnswerSink` port). Contract: eval/schemas/answer_v1.schema.json,
decision record 0002. `Answer` already has the format's fields."""

from pathlib import Path

from app.core.answering.model import Answer


class AnswerV1Writer:
    """Appends one JSON line per answer to `path`."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()  # a run with no questions still leaves an (empty) answers file

    def write(self, answer: Answer) -> None:
        with self._path.open("a", encoding="utf-8") as lines:
            lines.write(answer.model_dump_json() + "\n")
