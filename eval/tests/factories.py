"""Made-up questions and golden items in the dataset's shape. CI has no dataset, so every test
runs on these."""

import json
from pathlib import Path
from typing import Any

from stoa_eval.models import Answer, AnswerValue, GoldenItem, Question, QuestionType, Split, Unit
from stoa_eval.split import DEFAULT_EVAL_SHARE, DEFAULT_SEED, eval_groups, group_sizes


def _question(
    path: str, text: str, answer: AnswerValue, unit: Unit | None, type_: QuestionType
) -> Question:
    return Question(path=path, question=text, answer=answer, unit=unit, type=type_)


def make_questions() -> list[Question]:
    """Five sources, several languages and templates, several drawings per source."""
    rows: list[Question] = []
    for n in range(1, 7):
        plan = f"data/cubicasa5k/plan-{n}.png"
        rows += [
            _question(plan, "How many doors are shown on this floor plan?", n, "count", "count"),
            _question(plan, "Kuinka monta ovea pohjapiirustuksessa on?", n, "count", "count"),
            _question(plan, "How many saunas are on this floor plan?", n % 2, "count", "count"),
        ]
    for n in range(1, 6):
        floor = f"data/swiss_dwellings/site{n}_bldg{n}_floor{n}.pdf"
        rows += [
            _question(
                floor,
                f"What is the net floor area of room {n} ('Bad') in m²?",
                4.5 + n,
                "m2",
                "area",
            ),
            _question(
                floor,
                f"Wie gross ist die Nettofläche von Raum {n} («Bad») in m²?",
                4.5 + n,
                "m2",
                "area",
            ),
            _question(
                floor, "What is the net floor area of apartment A in m²?", 60.0 + n, "m2", "area"
            ),
        ]
    for name in ("alpha", "beta", "gamma"):
        model = f"data/ifc_models/demo-{name}_main.ifc"
        plan = f"data/ifc_models/demo-{name}_main_plan-01-ground.pdf"
        rows += [
            _question(
                model,
                "What is the total net volume of all walls on 'EG', in m³?",
                12.25,
                "m3",
                "volume",
            ),
            _question(
                plan,
                "Hvad er den samlede længde af alle vægge på 'Stue' i meter?",
                40.0,
                "m",
                "length",
            ),
        ]
    for name in ("house_arc", "house_mep", "tower_arc", "school_arc"):
        rows.append(
            _question(
                f"data/ifc_bench/{name}.ifc",
                "Which software was used to make this model?",
                "ArchiCAD 20",
                None,
                "text",
            )
        )
    for project in ("Gym", "Flats"):
        rows.append(
            _question(
                f"data/opening_design/{project}/Sheets/A-801 Schedules.pdf",
                "On sheet A-801, what is the area of room 101?",
                450,
                "ft2",
                "area",
            )
        )
    return rows


def write_questions(path: Path, rows: list[Question]) -> Path:
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
    return path


def golden_item(
    answer: AnswerValue,
    unit: Unit | None,
    type_: QuestionType,
    *,
    id_: int = 1,
    split: Split = "dev",
    source: str = "swiss_dwellings",
) -> GoldenItem:
    return GoldenItem(
        id=id_,
        path=f"data/{source}/plan-{id_}.pdf",
        question="q",
        answer=answer,
        unit=unit,
        type=type_,
        source=source,
        language="en",
        template="q",
        group=f"{source}/plan-{id_}",
        split=split,
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def oracle_answer(id_: int, question: Question, *, value: AnswerValue | None = None) -> Answer:
    """The golden answer for `question`, or `value` instead when given."""
    return Answer(
        id=id_,
        answer=question.answer if value is None else value,
        unit=question.unit,
        evidence=[],
        method="test",
        cost_usd=0.01,
        latency_s=1.0,
    )


def sealed_groups(rows: list[tuple[int, Question]]) -> set[str]:
    """The eval groups the default split gives `rows`."""
    sizes = group_sizes(question for _, question in rows)
    return eval_groups(sizes, DEFAULT_EVAL_SHARE, DEFAULT_SEED)
