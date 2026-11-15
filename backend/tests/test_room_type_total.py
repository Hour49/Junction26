"""A total area of rooms by a word the parser has no room type for (sample explorers, 2026-11-15):
"What is the total area of the offices?" answered every room of the sheet summed, at High (flat
site570: 798.81 m², truth 10 rooms printed Büro = 210.81; the IFC sample: 903.07 m² for "the
garages", one space printed 0GARAJE). Such a question is refused, never the sheet's total; a
label named without quotes ("rooms labelled Büro") sums the rooms printed so."""

import pytest

from app.adapters.question_templates import TemplateParser
from app.core.answering.answer import answer_question
from app.core.answering.model import Prior, Query, Question
from app.core.drawing.model import Drawing, Page, Room, RoomType, Scale
from app.core.pipeline.takeoff import known_quantities

FILE = "data/demo/offices.pdf"
BOX = (0.1, 0.1, 0.2, 0.2)
# (type, label, area): 64.18 m² indoor in all; two offices and a garage, of no type for either
ROOMS: tuple[tuple[RoomType, str, float], ...] = (
    ("other", "Büro", 10.0),
    ("other", "Büro", 12.0),
    ("other", "0GARAJE", 19.18),
    ("bedroom", "Schlafzimmer", 15.0),
    ("kitchen", "Küche", 8.0),
)
SHEET = Drawing(
    file=FILE,
    pages=(Page(page=1, width=100, height=100, unit="pt"),),
    scale=Scale(status="scaled", m_per_unit=0.01, text="1:100"),
    rooms=tuple(
        Room(id=f"r{n}", type=kind, label=label, page=1, box=BOX, area_m2=area)
        for n, (kind, label, area) in enumerate(ROOMS, start=1)
    ),
)
SHEET_TOTAL = 64.18


class NoPrior:
    def prior(self, source: str, family: str) -> Prior | None:
        return None


def answered(text: str) -> float | None:
    found = answer_question(
        Question(id=1, file=FILE, text=text), known_quantities(SHEET), TemplateParser(),
        lambda: 0.0, NoPrior(),
    )  # fmt: skip
    return None if found.answer is None else float(found.answer)


def test_the_sheet_total_asked_plainly_is_unchanged() -> None:
    assert answered("What is the total floor area?") == pytest.approx(SHEET_TOTAL)
    assert answered("What is the total area of all rooms?") == pytest.approx(SHEET_TOTAL)


@pytest.mark.parametrize(
    "text",
    [
        "What is the total area of the offices?",
        "What is the total area of the office?",
        "What is the total floor area of the offices?",
        "What is the total office area?",
        "What is the total area of the garages?",
        "What is the total garage area?",
        "What is the total area of the studios?",
        "What is the total area of all offices on this floor?",
    ],
)
def test_a_total_by_a_room_word_without_a_type_is_refused_not_every_room(text: str) -> None:
    assert answered(text) is None


@pytest.mark.parametrize(
    ("text", "total"),
    [
        ("What is the total area of all rooms labelled Büro?", 22.0),
        ("What is the total area of all rooms labelled 'Büro'?", 22.0),
        ("What is the total area of the rooms named 0GARAJE?", 19.18),
        ("What is the total area of all rooms labelled Schlafzimmer?", 15.0),
        ("How many rooms are labelled Büro?", 2),
    ],
)
def test_a_label_named_without_quotes_sums_the_rooms_printed_so(text: str, total: float) -> None:
    assert answered(text) == pytest.approx(total)


# review-754 point 3: a number or "both" before the room word says how many, not which, and
# "living", "habitable", "heated", "the home", "the main floor" name the sheet's rooms as before
@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("What is the total area of the two bedrooms?", "room:bedroom"),
        ("What is the total area of both bathrooms?", "room:bathroom"),
        ("What is the total area of the 2 bedrooms?", "room:bedroom"),
        ("What is the total area of all three kitchens?", "room:kitchen"),
    ],
)
def test_a_count_before_a_room_type_keeps_the_type(text: str, subject: str) -> None:
    assert TemplateParser().parse(text) == Query(measure="area", subject=subject)


@pytest.mark.parametrize(
    "text",
    [
        "What is the total living area?",
        "What is the total habitable area?",
        "What is the total heated area?",
        "What is the total residential area?",
        "What is the total area of the home?",
        "What is the total area of the property?",
        "What is the total area of the main floor?",
    ],
)
def test_the_sheet_total_in_other_words_is_its_indoor_total(text: str) -> None:
    assert answered(text) == pytest.approx(SHEET_TOTAL)


def test_a_count_before_an_unknown_room_word_is_still_refused() -> None:
    assert answered("What is the total area of the two offices?") is None


# review-755: a sheet's word before an unknown room word ("main", "home", "internal") is read past,
# never the whole sheet's rooms for offices
@pytest.mark.parametrize(
    "text",
    [
        "What is the total area of the main offices?",
        "What is the total area of the home office?",
        "What is the total area of the internal offices?",
    ],
)
def test_a_sheet_word_before_an_unknown_room_word_is_still_refused(text: str) -> None:
    assert answered(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "What is the total area of all rooms on this floor?",
        "What is the total area of the home in m²?",
    ],
)
def test_the_phrase_ends_where_its_place_or_unit_starts(text: str) -> None:
    assert answered(text) == pytest.approx(SHEET_TOTAL)
