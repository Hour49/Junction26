import pytest

from stoa_eval.families import UNDETERMINED, group_of, language_of, source_of, template_of


def test_template_masks_names_numbers_and_apartment_letters() -> None:
    assert template_of("Net area of room 3 ('Bad') in m²?") == "Net area of room <N> (<Q>) in m²?"
    assert template_of("Raum 12 («Küche») und „EG“ 1,5") == "Raum <N> (<Q>) und <Q> <N>"
    assert template_of("Area of apartment B?") == "Area of apartment <L>?"
    assert template_of("Combien d'appartements sur l'étage ?") == (
        "Combien d'appartements sur l'étage ?"
    )
    assert template_of("Room 2 ('Cage d'escalier') in m²?") == "Room <N> (<Q>) in m²?"
    assert template_of("the women's and men's rooms") == "the women's and men's rooms"


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("How many doors are shown on this floor plan?", "en"),
        ("Kuinka monta ovea pohjapiirustuksessa on?", "fi"),
        ("Wie viele Türen sind im Grundriss <Q> dargestellt?", "de"),
        ("Combien de fenêtres sont dessinées sur ce plan ?", "fr"),
        ("Qual è la superficie netta del locale <N> (<Q>) in m²?", "it"),
        ("¿Cuál es el número de puertas en el modelo <Q>?", "es"),
        ("Hvor mange døre er vist på plantegningen for <Q>?", "da"),
        ("Hoeveel deuren bevat het model <Q>?", "nl"),
        ("Mitu ust on mudelis <Q>?", "et"),
        ("Ile drzwi znajduje się w modelu <Q>?", "pl"),
        ("Care este numărul de ferestre din modelul <Q>?", "ro"),
        ("<Q> <N>?", UNDETERMINED),
    ],
)
def test_language_of(question: str, language: str) -> None:
    assert language_of(question) == language


def test_group_keeps_one_drawing_or_building_together() -> None:
    assert group_of("data/cubicasa5k/plan-1.png") == "cubicasa5k/plan-1"
    assert group_of("data/swiss_dwellings/s1_b2_f3.pdf") == group_of(
        "data/swiss_dwellings/s1_b2_f3.dxf"
    )
    assert group_of("data/ifc_models/demo-x_main.ifc") == "ifc_models/demo-x"
    assert group_of("data/ifc_models/demo-x_main_plan-01-ground.pdf") == "ifc_models/demo-x"
    assert group_of("data/ifc_bench/sixty5_arc.ifc") == group_of("data/ifc_bench/sixty5_str.ifc")
    assert group_of("data/opening_design/Gym/Sheets/A-801.pdf") == "opening_design/Gym"
    assert group_of("data/cubicasa5k/plan-1.png") != group_of("data/cubicasa5k/plan-2.png")


def test_source_needs_a_dataset_path() -> None:
    assert source_of("data/habs/sheet.pdf") == "habs"
    with pytest.raises(ValueError, match="data/<source>"):
        source_of("habs/sheet.pdf")
