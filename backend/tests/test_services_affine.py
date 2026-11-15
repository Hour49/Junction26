"""The sheet-to-plan map of a services picture (services-follow.md, SFPW-5)."""

import pytest

from app.core.services.model import Affine, Pairing


@pytest.mark.parametrize(
    "m",
    [
        Affine(),
        Affine(a=0.5, c=0.1, e=2.0, f=-0.3),  # scale and shift
        Affine(a=0.866, b=-0.5, c=0.2, d=0.5, e=0.866, f=0.1),  # a 30° rotation and shift
    ],
)
def test_the_affine_map_inverts(m: Affine) -> None:
    for p in [(0.0, 0.0), (0.25, 0.75), (1.0, 1.0)]:
        back = m.inverse().apply(m.apply(p))
        assert back == pytest.approx(p, abs=1e-9)


def test_a_folding_map_has_no_inverse() -> None:
    with pytest.raises(ValueError, match="folds the page"):
        Affine(a=1, b=2, d=2, e=4).inverse()


def test_the_pairings_map_is_not_in_the_api() -> None:
    paired = Pairing(drawing_id="d", page=1, paired_by="same_page", reason="the plan's own page",
                     to_plan=Affine())  # fmt: skip
    assert "to_plan" not in paired.model_dump()
    assert paired.model_dump()["score"] is None
