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


def test_a_printed_room_code_in_parentheses_names_one_room() -> None:
    living = Query(measure="area", subject="room", name="OH")
    assert PARSE("What is the floor area of the living room (OH) in square metres?") == living
    assert PARSE("How large is the main room (OH) in square metres?") == living
    assert PARSE("What is the area of the kitchen (K) in square metres?") == Query(
        measure="area", subject="room", name="K"
    )
    # a lower-case aside is a hint, not a code; a count keeps its own meaning
    assert isinstance(PARSE("What is the area of the rooms (all of them) in m²?"), Unsupported)
    assert PARSE("How many bedrooms (MH) are there?") == Query(subject="room:bedroom")


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
        subject="beam", model=True
    )
    assert PARSE("Wie viele Türen enthält das Modell „House“?") == Query(subject="door", model=True)


@pytest.mark.parametrize(
    "text",
    [
        "How many electrical sockets are shown on this plan?",
        "What is the ceiling height of room 4.07?",
        "Who owns apartment B?",
        "What is the length in metres of the longest wall?",
        "What is the total length of the exterior walls in metres?",
        "Wie viele Steckdosen sind eingezeichnet?",
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
        "What are the key building metrics including total elements, number of spaces, and "
        "building levels with their elevations?",
    ],
)
def test_a_subset_breakdown_or_unquoted_place_is_unsupported_not_the_whole_count(
    text: str,
) -> None:
    assert isinstance(PARSE(text), Unsupported)


@pytest.mark.parametrize(
    "text",
    [
        "How many doors and windows are there?",
        "How many doors are there near the window?",
        "How many doors does the kitchen have?",
        '<img src=x onerror="window.x=1">How many doors are there?',
    ],
)
def test_a_count_never_drops_part_of_the_question(text: str) -> None:
    """R1-5-2: these were answered as "door count" (or "window count") with no caveat."""
    assert isinstance(PARSE(text), Unsupported)


def test_room_types_and_rooms_named_as_included_still_count() -> None:
    assert PARSE("How many separate WC rooms (toilet rooms marked WC) are there?") == Query(
        subject="room:wc"
    )
    assert PARSE("How many sinks are there, kitchen and bathrooms included?") == Query(
        subject="sink"
    )
    assert PARSE("<b>How many doors are there?</b>") == Query(subject="door")


def test_a_question_about_the_building_is_about_the_model_not_the_sheet() -> None:
    assert PARSE("How many doors are there in this building?") == Query(subject="door", model=True)


def test_the_largest_room_of_a_label_or_type_by_area() -> None:
    by_label = Query(measure="area", subject="room", label="MH", largest=True)
    assert PARSE("Kuinka suuri on suurin makuuhuone (MH) neliömetreinä?") == by_label
    by_type = Query(measure="area", subject="room:kitchen", largest=True)
    assert PARSE("How big is the biggest kitchen, in m2?") == by_type
    for other in (
        "What is the largest door width on this plan?",  # not a room area
        "How many rooms does the largest apartment have?",  # a count
        "What is the area of the largest room?",  # which rooms
        "What is the area of the smallest bedroom?",  # only the largest is taken off
    ):
        assert isinstance(PARSE(other), Unsupported), other


def test_how_long_a_room_is_by_its_name_or_its_type() -> None:
    assert PARSE("How long is the living room (OH) along its longer side, in metres?") == Query(
        measure="length", subject="room", name="OH"
    )
    assert PARSE("Kuinka pitkä on parvekkeen pitkä sivu metreinä?") == Query(
        measure="length", subject="room:balcony"
    )
    assert isinstance(PARSE("In room 'A1', what is the length of the walls?"), Unsupported)
    assert isinstance(PARSE("How long is the room?"), Unsupported)


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("What is the area of the kitchen?", "room:kitchen"),
        ("What is the area of the kitchen in square metres?", "room:kitchen"),
        ("What is the net floor area of the kitchen?", "room:kitchen"),
        ("What is the area of the Küche?", "room:kitchen"),
        ("How large is the bathroom in m²?", "room:bathroom"),
    ],
)
def test_an_area_of_a_room_named_by_its_type_asks_for_that_room(text: str, subject: str) -> None:
    # R1-3-4 (user, 2026-11-14 via the orchestrator): answered when exactly one room of the type
    # is on the drawing (review/ask.py resolves it), else refused with the rooms that match
    assert PARSE(text) == Query(measure="area", subject=subject)


def test_the_apartment_without_a_letter_and_a_living_room_by_its_code() -> None:
    whole = Query(measure="area", subject="apartment")
    assert (
        PARSE("What is the floor area of the apartment in m², not counting the balcony?") == whole
    )
    assert PARSE("What is the floor area of the apartment in m²?") == whole
    assert PARSE("Kuinka suuri on olohuoneen (OH) pinta-ala neliömetreinä?") == Query(
        measure="area", subject="room", name="OH"
    )


SHEET_TOTAL = Query(measure="area", subject="room", indoor=True)


@pytest.mark.parametrize(
    "text",
    [
        "What is the total floor area?",
        "What is the total indoor floor area?",
        "What is the total area of all rooms?",
        "What is the total floor area in m²?",
        "What is the floor area of this plan?",
    ],
)
def test_the_sheet_s_floor_area_asked_plainly_is_its_indoor_total(text: str) -> None:
    # Stoa's one sheet total: "the total net floor area ... of all numbered indoor rooms"
    assert PARSE(text) == SHEET_TOTAL


@pytest.mark.parametrize(
    "text",
    [
        "What is the total gross floor area of the building?",
        "What is the building's footprint area?",
        "What is the total net floor area of the building?",
        "What is the total area of the sterilization rooms?",
    ],
)
def test_a_gross_footprint_building_or_named_rooms_area_is_not_the_sheet_total(text: str) -> None:
    assert isinstance(PARSE(text), Unsupported)
