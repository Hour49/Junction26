"""The Finnish pack cites the decree in force: YMa 631/2024 (asuin-, majoitus- ja työtiloista,
under the Building Act 751/2023, in force 2025-01-01), which replaced 1008/2017 (board #220,
Tudor's researcher). Quotes as printed on Finlex (open data AKN of 2024/631, read 2026-11-14;
Finlex puts a no-break space between "7" and "neliömetriä")."""

from app.adapters.rule_packs import load_packs
from app.settings import Settings

URL = "https://www.finlex.fi/fi/lainsaadanto/2024/631"
DECREE = "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista 631/2024"
CITED = {
    "fi-habitable-room-area": (
        f"{DECREE}, 4 § 2 mom.",
        "Asuin- ja majoitushuoneen ja työtilan huonealan on kuitenkin aina oltava vähintään 7 "
        "neliömetriä.",
    ),
}


def fi_pack():
    return next(pack for pack in load_packs(Settings().rule_packs_dir) if pack.id == "fi")


def test_the_7_m2_rule_cites_631_2024_4_2_word_for_word() -> None:
    rule = next(rule for rule in fi_pack().rules if rule.id == "fi-habitable-room-area")
    ref, quote = CITED[rule.id]
    assert (rule.clause.ref, rule.clause.url, rule.clause.quote) == (ref, URL, quote)


def test_the_window_rule_cites_631_2024_5_1_word_for_word() -> None:
    windowed = [rule for rule in fi_pack().rules if "valoaukon" in rule.clause.quote]
    assert len(windowed) == 1
    clause = windowed[0].clause
    assert (clause.ref, clause.url) == (f"{DECREE}, 5 § 1 mom.", URL)
    assert (
        clause.quote
        == "Asuin- ja majoitushuoneen ikkunan valoaukon on oltava vähintään 1/10 huonealasta."
    )


def test_no_rule_cites_the_replaced_decree_1008_2017() -> None:
    pack = fi_pack()
    for rule in pack.rules:
        assert "1008/2017" not in rule.clause.ref + rule.clause.url + (
            rule.applies_to.note or ""
        ), rule.id
    assert "631/2024" in pack.law
