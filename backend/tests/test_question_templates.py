"""The `templates` question parser: synthetic questions in the dataset's languages to queries.

The questions are written for these tests (reworded, hints dropped, typos), not copied from the
dataset, so a pass means the parser reads meaning rather than one fixed template."""

import pytest

from app.adapters.question_templates import TemplateParser
from app.core.answering.model import (
    IN_ONE_ROOM,
    NO_SUBJECT,
    SEVERAL_ROOMS,
    SEVERAL_THINGS,
    Query,
    Unsupported,
)

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


@pytest.mark.parametrize(
    "text",
    [
        "How many space heaters are there?",
        "How many space heaters does the model have?",
        "How many space frames are there?",
        "How many space trusses are shown?",
        "How many space-heaters are there?",
    ],
)
def test_space_as_part_of_a_compound_noun_is_not_rooms(text: str) -> None:
    """Tudor's QA (#430 c6886348353): "space heaters" answered "room count: 1"."""
    assert isinstance(PARSE(text), Unsupported)  # refused, so the fact sheet may answer it


@pytest.mark.parametrize(
    "text",
    [
        "What is the total area covered by space heating?",
        "What is the total area of the space heating zones?",
        "What is the total floor area with space cooling?",
    ],
)
def test_an_area_of_a_space_service_is_refused_not_the_indoor_total(text: str) -> None:
    """review-470 S1: with "space" no room word in these compounds, a subjectless total area
    became every indoor room's area; a named service that is no room is refused."""
    assert isinstance(PARSE(text), Unsupported)


@pytest.mark.parametrize(
    "text", ["How many spaces are there?", "How many spaces does the model have?",
             "How many spaces are shown on this floor plan?"],
)  # fmt: skip
def test_spaces_alone_are_still_rooms(text: str) -> None:
    found = PARSE(text)
    assert isinstance(found, Query) and (found.measure, found.subject) == ("count", "room")


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
    assert PARSE("how many windwos are on this floorplan") == Query(
        subject="window", read_as=("'windwos' as 'windows'",)
    )
    assert PARSE("Wie viele Fenstre sind eingezeichnet?") == Query(
        subject="window", read_as=("'Fenstre' as 'fenster'",)
    )


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
        "How many doors are on the 1st floor?",  # counted the whole sheet (fable-rooms r10 10)
        "How many windows are there on floor 2?",
        "How many rooms are on level 3?",
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


# QA R2-2-2: a count of elements "in the <room>" counts inside one room, which the takeoff does
# not; a room it can't place ("kitchn") must not drop the scope and count the whole sheet.
@pytest.mark.parametrize(
    "text",
    [
        "How many windows are in the kitchn?",
        "How many windows are in the kitchen?",
        "How many windows are in the bedrom?",
        "How many doors are in the garage?",
        "How many sinks are in the utility room?",
    ],
)
def test_elements_counted_in_one_room_are_refused_whether_or_not_the_room_is_known(
    text: str,
) -> None:
    assert PARSE(text) == Unsupported(reason=IN_ONE_ROOM)


@pytest.mark.parametrize(
    "text",
    [
        "How many windows are in the plan?",
        "How many windows are shown on this floor plan?",
        "how many windows can you see on this floorplan",
        "How many windows are in the drawing?",
        "How many windows are on the sheet?",
    ],
)
def test_elements_counted_on_the_sheet_are_answered(text: str) -> None:
    assert PARSE(text) == Query(subject="window")


def test_how_big_asks_for_an_area() -> None:
    """R2-2-3: "How big is room 1.01?" was refused as no count, area, length or volume."""
    assert PARSE("How big is room 1.01?") == Query(measure="area", subject="room", name="1.01")
    assert PARSE("How large is the kitchen?") == Query(measure="area", subject="room:kitchen")


@pytest.mark.parametrize(
    "text",
    [
        "How big is bathroom 1.01?",  # a type word and the number
        "What is the area of WC 1.01?",
        "How big is Bagno 1.01?",  # a printed label the parser has no word for, and the number
        "Quanto è grande il Bagno 1.01 in m2?",
        "What is the net floor area of Stanza 1.01?",
    ],
)
def test_a_room_number_with_any_word_names_that_room(text: str) -> None:
    """Tudor's chat QA (#14, floor9178): the type word dropped the number, and a label the parser
    has no word for left no room named."""
    assert PARSE(text) == Query(measure="area", subject="room", name="1.01")


@pytest.mark.parametrize(
    "text",
    [
        "How big is Bagno 1.01 and Bagno 1.09?",
        "How big is bathroom 1.01 and 1.09?",
        "What is the total area of room 1.01 and room 1.09?",
        "How long are rooms 1.01 and 1.09?",
    ],
)
def test_an_area_or_length_naming_two_rooms_asks_for_one_at_a_time(text: str) -> None:
    """review-313 S1: "Bagno 1.01 and Bagno 1.09" answered 1.01's area alone, with no note."""
    assert PARSE(text) == Unsupported(reason=SEVERAL_ROOMS)


@pytest.mark.parametrize(
    "text",
    [
        "What is the area of 1.5 x 2.0?",
        "What is the area of 1.5x2.0?",
        "How big is it, 2.5 m high?",
        "How big is 1.20 m?",
        "Area of 1.2 acres?",
        "How big is 3.5m2?",
    ],
)
def test_a_number_with_a_unit_or_in_a_product_is_not_a_room_number(text: str) -> None:
    """review-313 S2: these read as "the area of room 1.5" and refused as a missing room."""
    assert PARSE(text) == Unsupported(reason=NO_SUBJECT)


def test_a_room_number_keeps_its_unit_of_answer_and_a_measure_beside_a_room_type_is_dropped() -> (
    None
):
    area = Query(measure="area", subject="room", name="1.01")
    assert PARSE("How big is Bagno 1.01 in m²?") == area
    assert PARSE("What is the area of room 1.01 in m2?") == area
    assert PARSE("How long is room 1.01 in m?") == Query(
        measure="length", subject="room", name="1.01"
    )
    assert PARSE("How big is the 3.5 m2 balcony?") == Query(measure="area", subject="room:balcony")


def test_a_room_number_alone_does_not_make_a_count_or_a_sheet_total() -> None:
    assert PARSE("How long is Bagno 1.01?") == Query(measure="length", subject="room", name="1.01")
    assert PARSE("How many are in 1.01?") == Unsupported(
        reason="no element, room or apartment named"
    )


@pytest.mark.parametrize(
    ("text", "subject", "name"),
    [
        ("How many doors does Bagno 1.01 have?", "door", "1.01"),
        ("How many doors are in room 1.01?", "door", "1.01"),
        ("How many windows does room 'Cucina' have?", "window", "Cucina"),
        ("How many showers and bathtubs are in room 1.01?", "shower+bathtub", "1.01"),
    ],
)
def test_a_count_with_a_room_number_or_name_counts_inside_that_room(
    text: str, subject: str, name: str
) -> None:
    """Tudor's chat QA: "How many doors does Bagno 1.01 have?" counted the whole sheet."""
    assert PARSE(text) == Query(measure="count", subject=subject, name=name)


def test_a_count_naming_two_rooms_or_two_things_in_one_room_is_refused() -> None:
    assert PARSE("How many doors are in rooms 1.01 and 1.09?") == Unsupported(reason=SEVERAL_ROOMS)
    assert PARSE("How many doors and windows does room 1.01 have?") == Unsupported(
        reason=SEVERAL_THINGS
    )
    assert PARSE("How many doors are there?") == Query(measure="count", subject="door")


def test_a_storage_room_is_a_room_type() -> None:
    assert PARSE("What is the area of the storage room?") == Query(
        measure="area", subject="room:storage"
    )
    assert PARSE("How many storage rooms are there?") == Query(subject="room:storage")


def test_plans_are_counted() -> None:
    """R2-2 note: "How many plans are there?" was refused though the takeoff counts plans."""
    assert PARSE("How many plans are there?") == Query(subject="plan")
    assert PARSE("How many floor plans does the sheet show?") == Query(subject="plan")


def test_a_room_number_after_level_is_not_a_floor() -> None:
    """Only a whole number after floor, storey or level names a floor: "level 1.5" keeps the
    parse it had (a room numbered 1.5; RoomByType._not_a_room reads it)."""
    assert PARSE("What is the area of level 1.5?") == Query(
        measure="area", subject="room", name="1.5"
    )


def test_a_room_number_keeps_its_sign_and_a_hyphen_after_a_word_joins() -> None:
    """review-354 re-check: "room -1.2" is the basement room -1.2 (its label keeps the sign), not
    room 1.2; "Zimmer-1.05" is room 1.05."""
    assert PARSE("What is the area of room -1.2?") == Query(
        measure="area", subject="room", name="-1.2"
    )
    assert PARSE("What is the area of Zimmer-1.05?") == Query(
        measure="area", subject="room", name="1.05"
    )
