"""dino_match: the template's sightings kept when they look like their own legend symbol."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.adapters.discipline_pictures import dino_match
from app.core.errors import InvalidInputError, NotFoundError
from app.core.ifc_facts import Spot
from app.core.picture_facts import LegendEntry, PictureReading, Sighting

W, H, S = 400, 200, 30  # page px, symbol px


def circle(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x, y, x + S, y + S), outline=0, width=3)


def cross(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.line((x, y, x + S, y + S), fill=0, width=3)
    draw.line((x + S, y, x, y + S), fill=0, width=3)


def ell(draw: ImageDraw.ImageDraw, x: int, y: int, turned: bool = False) -> None:
    if turned:  # a quarter turn: the foot on the top right
        draw.rectangle((x, y, x + S, y + 6), fill=0)
        draw.rectangle((x + S - 6, y, x + S, y + S), fill=0)
    else:
        draw.rectangle((x, y, x + 6, y + S), fill=0)
        draw.rectangle((x, y + S - 6, x + S, y + S), fill=0)


def box(x: int, y: int, pad: int = 0) -> tuple[float, float, float, float]:
    return ((x - pad) / W, (y - pad) / H, (x + S + pad) / W, (y + S + pad) / H)


def page() -> tuple[np.ndarray, tuple[LegendEntry, ...], dict[str, tuple[int, int]]]:
    """Legend on the left (circle, cross, ell); on the plan a circle, a cross, an ell turned a
    quarter, and a blank spot."""
    image = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(image)
    legend = []
    for i, (label, symbol) in enumerate((("light", circle), ("tap", cross), ("valve", ell))):
        symbol(draw, 10, 10 + 60 * i)
        legend.append(LegendEntry(label=label, group=None, line=False, box=box(10, 10 + 60 * i, 8)))
    spots = {"circle": (200, 30), "cross": (300, 30), "ell": (200, 120), "blank": (300, 120)}
    circle(draw, *spots["circle"])
    cross(draw, *spots["cross"])
    ell(draw, *spots["ell"], turned=True)
    return np.asarray(image), tuple(legend), spots


def reading(legend: tuple[LegendEntry, ...], seen: list[tuple[str, tuple[int, int]]]):
    sightings = tuple(
        Sighting(label=label, spot=Spot(page=1, box=box(*xy), reader="template"), score=0.8)
        for label, xy in seen
    )
    return PictureReading(reader="template", legend=legend, read=None, sightings=sightings)


# the fakes' cosines are not the model's: no tuned keep here; every kind confirmed
TOY = {"keep": 0.5, "keeps": {}, "kinds": None}


class Thumbnails:
    """A stand-in for DINOv2: every patch token is the crop's 8 x 8 thumbnail, centred."""

    def run(self, output_names, input_feed):
        batch = input_feed["pixel_values"]
        assert batch.shape[1:] == (3, dino_match.SIDE, dino_match.SIDE)
        grey = batch[:, 0].reshape(len(batch), 8, 14, 8, 14).mean(axis=(2, 4)).reshape(-1, 64)
        grey = grey - grey.mean(axis=1, keepdims=True)
        tokens = np.zeros((len(batch), 65, 384), np.float32)
        tokens[:, :, :64] = grey[:, None, :]
        return [tokens]


class Biased(Thumbnails):
    """Thumbnails without centring, on a large shared offset: what DINOv2's patches share across
    every crop. The mean patch then calls everything alike; the grid minus a blank's does not."""

    def run(self, output_names, input_feed):
        batch = input_feed["pixel_values"]
        grey = batch[:, 0].reshape(len(batch), 8, 14, 8, 14).mean(axis=(2, 4)).reshape(-1, 64)
        tokens = np.full((len(batch), 65, 384), 50.0, np.float32)
        tokens[:, 1:, :64] += grey[:, :, None] * np.eye(64, dtype=np.float32)[None]
        return [tokens]


def test_the_grid_minus_a_blank_drops_a_blank_despite_a_shared_offset() -> None:
    gray, legend, at = page()
    seen = [("light", at["circle"]), ("light", at["blank"])]
    kept = dino_match.confirm(gray, reading(legend, seen), Biased(), **TOY)
    assert [s.spot.box for s in kept.sightings] == [box(*at["circle"])]


def test_the_keep_is_per_kind() -> None:
    gray, legend, at = page()
    seen = [("light", at["circle"]), ("valve", at["ell"])]
    strict = {"valve": 1.01}  # no valve passes; the light keeps the default
    kept = dino_match.confirm(
        gray, reading(legend, seen), Thumbnails(), keep=0.5, keeps=strict, kinds=None
    )
    assert [s.label for s in kept.sightings] == ["light"]


def test_keeps_its_own_symbol_turned_and_drops_a_look_alike_and_a_blank() -> None:
    gray, legend, at = page()
    seen = [
        ("light", at["circle"]),
        ("light", at["cross"]),  # a tap read as a light
        ("valve", at["ell"]),  # turned a quarter
        ("light", at["blank"]),
    ]
    kept = dino_match.confirm(gray, reading(legend, seen), Thumbnails(), **TOY)
    assert [(s.label, s.spot.box) for s in kept.sightings] == [
        ("light", box(*at["circle"])),
        ("valve", box(*at["ell"])),
    ]
    assert kept.notes == ("dino: dropped 2 of 4 sightings",)


def test_a_label_without_a_legend_symbol_is_kept_and_nothing_seen_is_nothing_dropped() -> None:
    gray, legend, at = page()
    unknown = reading(legend, [("pump", at["blank"])])
    assert dino_match.confirm(gray, unknown, Thumbnails()).sightings == unknown.sightings
    empty = reading(legend, [])
    assert dino_match.confirm(gray, empty, Thumbnails()) == empty


def test_load_refuses_a_missing_or_different_model_file(tmp_path) -> None:
    with pytest.raises(NotFoundError):
        dino_match.load(tmp_path)
    (tmp_path / dino_match.FILE).write_bytes(b"not the model")
    with pytest.raises(InvalidInputError):
        dino_match.load(tmp_path)


@pytest.mark.skipif(
    not (dino_match.MODEL / dino_match.FILE).is_file(), reason="dinov2-small not downloaded"
)
def test_the_real_model_keeps_the_circle_and_drops_the_cross() -> None:
    gray, legend, at = page()
    seen = [("light", at["circle"]), ("light", at["cross"])]
    kept = dino_match.confirm(gray, reading(legend, seen), dino_match.load(), kinds=None)
    assert [s.spot.box for s in kept.sightings] == [box(*at["circle"])]


def labelled(gray_legend: tuple[LegendEntry, ...], labels: tuple[str, str, str], group=None):
    """The page's legend (circle, cross, ell) under other labels and one group heading."""
    return tuple(
        e.model_copy(update={"label": label, "group": group})
        for e, label in zip(gray_legend, labels, strict=True)
    )


def test_only_air_terminals_are_confirmed_not_labels_of_no_kind() -> None:
    """Tudor's bench (#543): a label of no IFC kind is mostly a valve or a fixture under a Dutch or
    brand name ('regelklep', 'kraan', 'Grohe_Rapid_SL', 'LOROX'); confirming them dropped valve
    and sanitary recall. They stay as the template read them, look-alikes and all."""
    gray, legend, at = page()
    for labels in (("regelklep", "kraan", "x"), ("Grohe_Rapid_SL", "LOROX", "x")):
        legend2 = labelled(legend, labels, group="Sanitair")
        seen = [(labels[0], at["cross"]), (labels[1], at["circle"]), (labels[0], at["blank"])]
        got = dino_match.confirm(gray, reading(legend2, seen), Thumbnails(), keep=0.5, keeps={})
        assert got.sightings == reading(legend2, seen).sightings, labels


def test_an_air_terminal_or_an_air_worded_label_is_confirmed() -> None:
    """'toevoer rooster' (a supply grille) names no IFC kind but air words: confirmed, as is a
    label under a ventilation heading; a light stays as read."""
    gray, legend, at = page()
    legend2 = labelled(legend, ("toevoer rooster", "light", "x"))
    seen = [
        ("toevoer rooster", at["circle"]),
        ("toevoer rooster", at["cross"]),
        ("light", at["cross"]),
    ]
    got = dino_match.confirm(gray, reading(legend2, seen), Thumbnails(), keep=0.5, keeps={})
    assert [(s.label, s.spot.box) for s in got.sightings] == [
        ("toevoer rooster", box(*at["circle"])),
        ("light", box(*at["cross"])),
    ]
    vent = labelled(legend, ("type A", "type B", "x"), group="Ventilatie")
    seen = [("type A", at["circle"]), ("type A", at["cross"])]
    got = dino_match.confirm(gray, reading(vent, seen), Thumbnails(), keep=0.5, keeps={})
    assert [s.spot.box for s in got.sightings] == [box(*at["circle"])]
    sup = labelled(legend, ("supply air diffuser", "b", "x"))
    seen = [("supply air diffuser", at["blank"])]
    assert (
        dino_match.confirm(gray, reading(sup, seen), Thumbnails(), keep=0.5, keeps={}).sightings
        == ()
    )
    assert frozenset({"air_terminal"}) == dino_match.CONFIRM_KINDS
