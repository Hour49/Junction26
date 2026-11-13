"""The `templates` question parser: synthetic questions in the dataset's languages to queries.

The questions are written for these tests (reworded, hints dropped, typos), not copied from the
dataset, so a pass means the parser reads meaning rather than one fixed template."""

import pytest

from app.adapters.question_templates import TemplateParser
from app.core.answering.model import Query, Unsupported

PARSE = TemplateParser().parse


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("How many doors can be seen on the plan?", "door"),
        ("Wie viele Fenster hat dieser Grundriss?", "window"),
        ("Combien de baignoires voit-on sur ce plan ?", "bathtub"),
        ("Quante docce ci sono in questa pianta?", "shower"),
        ("Kuinka monta WC-istuinta kuvassa on?", "toilet"),
        ("Montako erillistä WC-tilaa asunnossa on?", "room:wc"),
        ("How many separate WC rooms does the flat have?", "room:wc"),
        ("Count the toilets (WC) drawn here.", "toilet"),
        ("How many washbasins are there?", "sink"),
        ("Kuinka monta makuuhuonetta kuvassa on?", "room:bedroom"),
        ("How many kitchens are shown?", "room:kitchen"),
        ("Montako parveketta pohjakuvassa on?", "room:balcony"),
        ("How many saunas does this home have?", "sauna"),
        ("Laske yhteen suihkut ja kylpyammeet.", "shower+bathtub"),
        ("What is the total of showers and bathtubs? Add up both.", "shower+bathtub"),
        ("How many floors (storeys) are drawn on this sheet?", "plan"),
        ("Aus wie vielen Wohnungen besteht dieses Geschoss?", "apartment"),
        ("Hoeveel kolommen staan op deze tekening?", "column"),
        ("Ile schodów jest na rysunku?", "stair"),
    ],
)
def test_a_count_question_names_its_subject(text: str, subject: str) -> None:
    assert PARSE(text) == Query(measure="count", subject=subject)


def test_hints_and_excluded_clauses_are_not_the_subject() -> None:
    bathrooms = Query(measure="count", subject="room:bathroom")
    assert PARSE("Leaving out separate WC rooms, how many bathrooms are there?") == bathrooms
    assert (
        PARSE("How many bathrooms (not WC rooms) are on the plan, not counting WCs?") == bathrooms
    )
    assert PARSE("Laske kylpyhuoneet; erilliset WC-tilat jätetään pois.") == bathrooms
    sinks = Query(measure="count", subject="sink")
    assert PARSE("How many sinks are drawn, kitchen and bathroom together?") == sinks


def test_a_typo_in_the_subject_still_parses() -> None:
    assert PARSE("how many windwos are on this floorplan") == Query(subject="window")
    assert PARSE("Wie viele Fenstre sind eingezeichnet?") == Query(subject="window")


def test_a_quoted_label_counts_or_sums_the_rooms_with_that_label() -> None:
    assert PARSE("How many rooms labelled 'Bad' are on this floor?") == Query(
        subject="room", label="Bad"
    )
    assert PARSE("Combien de pièces désignées « Cage d'escalier » y a-t-il ?") == Query(
        subject="room", label="Cage d'escalier"
    )
    assert PARSE("Addiere die Nettoflächen aller Räume mit der Bezeichnung «Zimmer» in m².") == (
        Query(measure="area", subject="room", label="Zimmer")
    )


def test_a_room_number_names_one_room_and_its_quoted_label_is_an_aside() -> None:
    expected = Query(measure="area", subject="room", name="2.07")
    assert PARSE("Give the net area in m² of room 2.07 ('Küche').") == expected
    assert PARSE("Quelle est la surface de la pièce U1.03 (« Cave ») en m² ?") == Query(
        measure="area", subject="room", name="U1.03"
    )


def test_apartment_and_indoor_totals() -> None:
    apartment = Query(measure="area", subject="apartment", apartment="B")
    assert PARSE("Sum the rooms of apartment B without balconies; area in m²?") == apartment
    assert PARSE("Wie gross ist die Nettowohnfläche von Wohnung B?") == apartment
    assert PARSE("Qual è la superficie netta dell'appartamento B in m²?") == apartment
    assert PARSE("Total net area in m² of the numbered indoor rooms, shafts excluded?") == Query(
        measure="area", subject="room", indoor=True
    )


def test_ifc_questions_name_a_room_and_a_storey() -> None:
    expected = Query(measure="area", subject="room", name="Office (1.04)", storey="Level 1")
    assert PARSE("What is the net floor area of the room 'Office (1.04)' on 'Level 1'?") == expected
    assert PARSE("Kui suur on ruumi „Office (1.04)“ pind korrusel „Level 1“ (m²)?") == expected
    assert PARSE(
        "¿Cuál es la superficie útil del local «Office (1.04)» en la planta «Level 1»?"
    ) == (expected)
    assert PARSE("Hoeveel deuren staan er op de plattegrond van 'Level 1'?") == Query(
        subject="door", storey="Level 1"
    )
    assert PARSE("Wie viele Räume sind im Grundriss „EG“ dargestellt?") == Query(
        subject="room", storey="EG"
    )
    assert PARSE("Ile pomieszczeń jest na kondygnacji „0“? Podaj łączna powierzchnia w m².") == (
        Query(measure="area", subject="room", storey="0")
    )


def test_wall_and_slab_quantities_on_a_storey() -> None:
    assert PARSE("Wie lang sind alle Wände im Geschoss 'OG' zusammen?") == Query(
        measure="length", subject="wall", storey="OG"
    )
    assert PARSE("What is the total net side area of all walls on 'OG', in m²?") == Query(
        measure="area", subject="wall", storey="OG"
    )
    assert PARSE("Wat is het totale netto volume van alle vloeren op 'OG'?") == Query(
        measure="volume", subject="slab", storey="OG"
    )


def test_a_question_about_the_whole_model_is_marked_as_such() -> None:
    assert PARSE("How many beams are there in the model 'House'?") == Query(
        subject="beam", storey="House", model=True
    )
    assert PARSE("Wie viele Türen enthält das Modell „House“?") == Query(
        subject="door", storey="House", model=True
    )


@pytest.mark.parametrize(
    "text",
    [
        "How many electrical sockets are shown on this plan?",
        "What is the ceiling height of room 4.07?",
        "Who owns apartment B?",
        "What is the area of the kitchen in square metres?",
        "What is the length in metres of the longest wall?",
        "What is the total length of the exterior walls in metres?",
        "How many doors are listed in the door schedule?",
        "Wie viele Steckdosen sind eingezeichnet?",
        "What is the floor area of the apartment in m²?",
    ],
)
def test_a_question_without_a_takeoff_quantity_is_unsupported(text: str) -> None:
    assert isinstance(PARSE(text), Unsupported)


def test_danish_romanian_and_italian_questions_parse() -> None:
    assert PARSE("Hvad er nettoarealet af rummet 'Kontor (1.2)' på 'Stue' i m²?") == Query(
        measure="area", subject="room", name="Kontor (1.2)", storey="Stue"
    )
    assert PARSE("Hvad er den samlede længde af alle vægge på 'Stue' i meter?") == Query(
        measure="length", subject="wall", storey="Stue"
    )
    assert PARSE("Care este numărul de ferestre de pe planul nivelului 'Parter'?") == Query(
        subject="window", storey="Parter"
    )
    assert PARSE("Qual è il numero di muri nella pianta del piano 'Terra'?") == Query(
        subject="wall", storey="Terra"
    )


@pytest.mark.parametrize(
    "text",
    [
        "How many meeting rooms are available?",
        "How many X-RAY rooms are there in total?",
        "How many interior doors are there?",
        "How many steps does the stair in house A have?",
        "How many toilets are on the ground floor?",
        "How many windows are there on the north facade?",
        "How many rooms have access to outdoor space?",
        "What door types are present, and how many of each type?",
        "What is the total volume of concrete in slabs, columns and beams?",
    ],
)
def test_a_subset_breakdown_or_unquoted_place_is_unsupported_not_the_whole_count(
    text: str,
) -> None:
    assert isinstance(PARSE(text), Unsupported)


def test_a_question_about_the_building_is_about_the_model_not_the_sheet() -> None:
    assert PARSE("How many doors are there in this building?") == Query(subject="door", model=True)
