# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CubiCasa extraction gold (extraction_v1) for the Stoa dataset.

Dev files: elements and rooms from the public CubiCasa5K `model.svg` (read straight from the zip).
Eval files: `truth: counts` built from the question answers only (decision 0003: eval SVGs are never read).

Imports: standard library only (zipfile, xml.etree, json, re, struct). Reads the CubiCasa5K zip from Zenodo
record 2613548 (CC BY-NC-SA 4.0, research use). No PyMuPDF, no Ultralytics, no ifcopenshell.

    uv run prototypes/extraction-gold/cubicasa_gold.py --dataset data/stoa/full/junction-dataset \
        --split data/stoa/split --out data/stoa/extraction_gold/cubicasa5k [--zip data/external/cubicasa5k/cubicasa5k.zip]
    ... --check     also print the rule check (dataset answers vs counts from the gold files)
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://www.w3.org/2000/svg}"
TEMPLATES = {  # EN question prefix -> template key
    "How many windows": "windows",
    "How many floors": "floors",
    "How many toilet bowls": "wc_seats",
    "How many sinks": "sinks",
    "How many showers and bathtubs": "showers_baths",
    "How many doors": "doors",
    "How many saunas": "saunas",
    "How many kitchens": "kitchens",
    "How many bedrooms": "bedrooms",
    "How many bathrooms": "bathrooms",
    "How many separate WC": "wc_rooms",
    "How many balconies": "balconies",
}
# eval files (truth: counts): template -> count key. Showers and baths are one combined question.
COUNT_KEY = {
    "windows": "window",
    "floors": "plan",
    "wc_seats": "toilet",
    "sinks": "sink",
    "showers_baths": "shower",
    "doors": "door",
    "saunas": "room:sauna",
    "kitchens": "room:kitchen",
    "bedrooms": "room:bedroom",
    "bathrooms": "room:bathroom",
    "wc_rooms": "room:wc",
    "balconies": "room:balcony",
}


# Scale evidence seen by eye on 74 dev images (review-1): stem -> kinds of evidence (extraction_v1 scale.evidence names; "unclear" = unreadable).
SCALE_LOOKED = {
    "high_quality_architectural-12501": [],
    "colorful-12214": [],
    "high_quality-11271": [],
    "colorful-1953": [],
    "high_quality_architectural-2580": ["printed_areas", "dimension_lines"],
    "high_quality-20059": ["not_to_scale_note"],
    "colorful-11565": [],
    "high_quality_architectural-11461": ["printed_areas"],
    "high_quality-7522": [],
    "high_quality_architectural-9352": [],
    "high_quality-8530": [],
    "high_quality_architectural-7578": ["dimension_lines"],
    "colorful-11774": [],
    "colorful-7513": ["not_to_scale_note"],
    "high_quality-14424": [],
    "high_quality_architectural-11862": [],
    "high_quality_architectural-13802": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-14874": ["printed_areas", "dimension_lines"],
    "high_quality-17": ["not_to_scale_note"],
    "high_quality-9835": [],
    "high_quality_architectural-6074": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-1364": ["printed_areas"],
    "high_quality_architectural-1576": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-14052": ["dimension_lines"],
    "high_quality_architectural-7798": ["dimension_lines"],
    "high_quality-10669": ["not_to_scale_note"],
    "high_quality_architectural-14587": ["printed_areas"],
    "high_quality_architectural-12598": ["not_to_scale_note"],
    "high_quality-6256": [],
    "high_quality_architectural-769": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-12544": ["printed_areas"],
    "high_quality_architectural-9976": ["printed_areas"],
    "colorful-13019": [],
    "high_quality_architectural-8218": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-10217": ["not_to_scale_note"],
    "high_quality-3920": ["not_to_scale_note"],
    "high_quality_architectural-9837": [],
    "high_quality_architectural-13717": ["dimension_lines"],
    "high_quality_architectural-9104": ["dimension_lines"],
    "high_quality_architectural-7084": ["dimension_lines"],
    "high_quality-9336": [],
    "high_quality_architectural-6322": ["dimension_lines"],
    "high_quality-12896": [],
    "high_quality_architectural-14561": [
        "printed_areas",
        "dimension_lines",
        "scale_text",
    ],
    "colorful-10706": [],
    "high_quality_architectural-10719": ["printed_areas"],
    "high_quality-10666": ["unclear"],
    "colorful-444": ["not_to_scale_note"],
    "high_quality_architectural-3778": ["printed_areas"],
    "high_quality-13742": [],
    "high_quality-3106": [],
    "high_quality_architectural-10267": [],
    "colorful-11397": [],
    "high_quality_architectural-486": [],
    "high_quality_architectural-5901": ["printed_areas"],
    "colorful-9392": ["not_to_scale_note"],
    "high_quality-5972": [],
    "high_quality-12137": [],
    "high_quality-7539": [],
    "high_quality_architectural-13791": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-10149": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-13113": [],
    "high_quality_architectural-10203": ["printed_areas"],
    "colorful-10312": [],
    "high_quality-215": [],
    "high_quality-1651": ["not_to_scale_note"],
    "high_quality_architectural-3864": ["printed_areas", "dimension_lines"],
    "high_quality_architectural-11404": ["printed_areas", "dimension_lines"],
    "high_quality-3954": [],
    "colorful-13577": [],
    "high_quality-13094": [],
    "high_quality_architectural-4697": [],
    "high_quality_architectural-11153": ["printed_areas"],
    "high_quality_architectural-8502": ["printed_areas"],
}

# Hand scales (status scaled): stem -> (metres per svg unit, evidence, printed scale text, source). Gold rule: at least two printed room areas
# agree within 1% (largest subset within +-1% of its median; the median of that subset is the value). arch-1576 failed (2 rooms, 2.3% apart) and is dropped.
HAND_SCALES = {
    "high_quality_architectural-14874": (
        0.00966,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 6 of 9 printed room areas agree within 1% (K 12,2 OH 17,9 ET 6,8 PH 3,6 WC 2,0 MH 10,6/12,5/10,7 m2); outer dimension 10930 mm vs 10,73 m interior + walls",
    ),
    "high_quality_architectural-11461": (
        0.00995,
        ["printed_areas"],
        None,
        "hand: 4 of 5 printed room areas agree within 1% (KEITTIO 13 ET 5,5 OH 23 MH 12,5 m2)",
    ),
    "high_quality_architectural-13802": (
        0.00971,
        ["printed_areas"],
        None,
        "hand: 3 of 3 printed room areas agree within 1% (WC 1,6 KPH 3,3 KHH 9 m2)",
    ),
    "high_quality_architectural-9976": (
        0.00977,
        ["printed_areas"],
        None,
        "hand: 9 of 11 printed room areas agree within 1% (mh 12,4 11,4 8,6 vh 3,8 wc 3,6 khh 7,8 pukut 7,4 pesut 8,1 tk 7,0 m2)",
    ),
    "high_quality_architectural-769": (
        0.00999,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 4 of 7 printed room areas agree within 1% (VIERASH 11,7 OLOH 24,0 TK 3,0 VH 2,5 m2); total width 14915 mm printed",
    ),
    "high_quality_architectural-32": (
        0.00952,
        ["printed_areas"],
        None,
        "hand: 4 of 5 printed room areas agree within 1% (MH 13,9 TEKN.TILA 8,4 AT 20,3 MH 10,9 m2), skewed scan",
    ),
    "high_quality_architectural-11250": (
        0.01035,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 4 of 7 printed room areas agree within 1% (PH 4,2 PKH 5,3 MH 8,1 TK 6,1 m2)",
    ),
    "high_quality_architectural-14087": (
        0.01031,
        ["printed_areas", "dimension_lines", "scale_text"],
        "1:50",
        "hand: 4 of 7 printed room areas agree within 1% (MH 16 KH 6,6 PH 6,9 TYOH 11,5 m2); sheet text 1:50, not usable alone for pixels",
    ),
    "high_quality_architectural-13666": (
        0.01011,
        ["printed_areas", "dimension_lines"],
        None,
        "hand: 4 of 6 printed room areas agree within 1% (MH 13,3 MH 14,0 OH 26,4 TEKN 3,8 VAR 28,6 m2); dimension-label spacing gives 0.0354 m/px (-2%, reading error about 2%); the sheet's 1:50 heads the chimney/fireplace detail, not the plan",
    ),
    "high_quality_architectural-14561": (
        0.00965,
        ["printed_areas", "dimension_lines", "scale_text"],
        "1:50",
        "hand: 4 of 9 printed room areas agree within 1% (K 9,5 OH 22,0 PH 4,0 WC 2,5 KHH 9,5 VAR 10,0 m2); sheet text 1:50, not usable alone for pixels",
    ),
}
HAND_TRAP = {"high_quality_architectural-13666"}  # sheet 1:50 labels a detail
DROPPED_SCALES = {
    "high_quality_architectural-1576": "printed room areas TUPA/KEITTIO 25,9 and ET 9,2 m2 disagree by 2.3% (> 1%); dropped from the scale cases"
}
# model.svg units are about 1 cm: 0.0095-0.0104 m/unit on the 10 hand-scaled plans (mean abs error 2.5%, max 4.8%). Reference only, never a 2% truth.
SVG_M_PER_UNIT = 0.01

DIM_LINES: dict = {}  # stem -> review-2 case, filled in main()


def make_scale(stem: str, ws: int, W: int):
    """scale object (status scaled / no_scale / not_to_scale) and notes for a dev file. m per Stoa PNG pixel."""
    ref = round(SVG_M_PER_UNIT * ws / W, 7)
    if stem in HAND_SCALES:
        mu, ev, text, src = HAND_SCALES[stem]
        return {
            "status": "scaled",
            "m_per_unit": round(mu * ws / W, 7),
            "evidence": ev,
            "text": text,
            "source": src,
        }, (
            ["trap: printed 1:50 belongs to a detail, not the plan"]
            if stem in HAND_TRAP
            else []
        )
    if stem in DIM_LINES:
        c = DIM_LINES[stem]
        if c.get("m_per_unit") is None:  # review-2 dropped it (anisotropic scan)
            ref = round(SVG_M_PER_UNIT * ws / W, 7)
            return {
                "status": "no_scale",
                "m_per_unit": None,
                "evidence": [],
                "text": None,
                "source": "dropped from the scale cases",
                "reference_m_per_unit": ref,
            }, [
                "scale dropped: anisotropic scan 2%: " + c.get("note", ""),
                "scale not reviewed",
            ]
        notes = (
            ["trap: printed 1:50 belongs to a detail, not the plan"]
            if c.get("trap")
            else []
        )
        return {
            "status": "scaled",
            "m_per_unit": c["m_per_unit"],
            "evidence": ["dimension_lines"],
            "text": None,
            "source": "dimension lines, "
            + "; ".join(str(x) for x in c.get("checks", []))
            + (" | " + c["note"] if c.get("note") else ""),
        }, notes
    kinds = SCALE_LOOKED.get(stem)
    if stem in DROPPED_SCALES:
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "dropped from the scale cases",
            "reference_m_per_unit": ref,
        }, [DROPPED_SCALES[stem], "scale not reviewed"]
    if kinds == ["not_to_scale_note"]:
        return {
            "status": "not_to_scale",
            "m_per_unit": None,
            "evidence": ["not_to_scale_note"],
            "text": None,
            "source": "the sheet says it is not to scale (e.g. suuntaa-antava, ei mittakaavassa)",
        }, []
    if kinds == []:
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "looked at the image: no scale evidence",
            "reference_m_per_unit": ref,
        }, []
    if kinds:  # evidence seen but no verified value
        what = "unreadable text" if kinds == ["unclear"] else ", ".join(kinds)
        return {
            "status": "no_scale",
            "m_per_unit": None,
            "evidence": [],
            "text": None,
            "source": "scale not verified",
            "reference_m_per_unit": ref,
        }, [
            "scale not reviewed",
            f"image shows ({what}) but no value was verified; excluded from scale cases",
        ]
    return {
        "status": "no_scale",
        "m_per_unit": None,
        "evidence": [],
        "text": None,
        "source": "not reviewed",
        "reference_m_per_unit": ref,
    }, ["scale not reviewed"]


# ---------- all-image scale and room areas (brief scale-all, 2026-11-13) ----------
DOOR_M = 0.80  # median door-leaf width (review-1: median 0.794 m over 20 scaled plans, 72% of doors within 10%)
# printed per-room areas read by hand: stem -> [(label, m2)]; matched to the SVG room by label and closest polygon area
PRINTED = {
    "high_quality_architectural-14874": [
        ("K", 12.2),
        ("OH", 17.9),
        ("ET", 6.8),
        ("PH", 3.6),
        ("WC", 2.0),
        ("MH", 10.6),
        ("MH", 12.5),
        ("MH", 10.7),
    ],
    "high_quality_architectural-11461": [
        ("K", 13.0),
        ("ET", 5.5),
        ("OH", 23.0),
        ("MH", 12.5),
    ],
    "high_quality_architectural-13802": [("WC", 1.6), ("KPH", 3.3), ("KHH", 9.0)],
    "high_quality_architectural-9976": [
        ("MH", 12.4),
        ("MH", 11.4),
        ("MH", 8.6),
        ("VH", 3.8),
        ("WC", 3.6),
        ("KHH", 7.8),
        ("TK", 7.0),
    ],
    "high_quality_architectural-769": [
        ("VIERASH", 11.7),
        ("OLOH", 24.0),
        ("TK", 3.0),
        ("VH", 2.5),
    ],
    "high_quality_architectural-32": [
        ("MH", 13.9),
        ("TEKN.TILA", 8.4),
        ("AT", 20.3),
        ("MH", 10.9),
    ],
    "high_quality_architectural-11250": [
        ("PH", 4.2),
        ("PKH", 5.3),
        ("MH", 8.1),
        ("TK", 6.1),
    ],
    "high_quality_architectural-14087": [
        ("MH", 16.0),
        ("KH", 6.6),
        ("PH", 6.9),
        ("TYOH", 11.5),
    ],
    "high_quality_architectural-13666": [
        ("MH", 13.3),
        ("MH", 14.0),
        ("OH", 26.4),
        ("TEKN", 3.8),
        ("VAR", 28.6),
    ],
    "high_quality_architectural-14561": [
        ("K", 9.5),
        ("OH", 22.0),
        ("PH", 4.0),
        ("WC", 2.5),
        ("KHH", 9.5),
        ("VAR", 10.0),
    ],
}


# hand reviews by review-1 (full-size images). stem -> dict(status, m_per_unit (m per Stoa PNG px), uncertainty,
# evidence, text, source, printed [(label, m2, near (x, y) page fraction or None)], notes [str])
def _hr(**kw):
    return kw


HAND_REVIEW_1: dict = {
    "colorful-30": _hr(
        status="not_to_scale",
        evidence=["not_to_scale_note"],
        source='sheet text "SUUNTAA-ANTAVA, EI MITTAKAAVASSA" (approximate, not to scale); no printed areas, no dimensions',
    ),
    "high_quality-12278": _hr(
        status="estimated",
        source="no scale text, no printed areas, no dimensions on the sheet (agency logo only)",
    ),
    "high_quality-3650": _hr(
        status="estimated",
        source="no scale text, no printed areas, no dimensions (sheet scanned upside down)",
    ),
    "high_quality-3845": _hr(
        status="estimated",
        source="no scale text, no printed areas, no dimensions (upside down, pen markings)",
    ),
    "high_quality-8329": _hr(
        status="estimated",
        source="no scale text, no printed areas, no dimensions; two storeys on one sheet (1 krs, 2. krs). SVG unit and door check disagree by about 40%, so the value is weak",
    ),
    "high_quality_architectural-10036": _hr(
        status="estimated",
        m_per_unit=0.0189,
        uncertainty=0.04,
        evidence=["printed_areas", "dimension_lines"],
        source="two printed 12 m2 rooms give 0.0190 and 0.0188 m/px; the single overall label 19600 mm (no tick lines visible) spans about 1035 px of the house, 0.0189 m/px; SVG unit 0.0182 and doors 0.0214 are 4% and 13% away",
        printed=[
            ("", 12.0, (215 / 1314, 110 / 613)),
            ("", 12.0, (190 / 1314, 305 / 613)),
        ],
        notes=[
            "'27,5 m2' is printed beside the second 12 m2 room and is not a per-room area (not used)"
        ],
    ),
    "high_quality_architectural-11841": _hr(
        status="estimated",
        m_per_unit=0.01481,
        uncertainty=0.04,
        evidence=["dimension_lines"],
        source="bottom chain 3450/1450/2000 = 6900 mm over 466 px (ticks x=49, 281, 381, 515): 14.87, 14.50, 14.93 mm/px, total 14.81; the right chain 1950/2100/1950 = 6000 mm over 390 px gives 15.4 (3.8% apart, so not scaled); SVG unit 14.56",
    ),
    "high_quality_architectural-13436": _hr(
        status="estimated",
        m_per_unit=0.0119,
        uncertainty=0.06,
        evidence=["printed_areas"],
        source="printed apartment total 'B46 1H+KT 25,0 m2' against the sum of the five indoor room polygons (176163 px2) gives 0.01191 m/px (polygons run 0-8% above net area); SVG unit 0.01176; doors 0.01065 (-10%); no per-room areas",
        notes=[
            "cropped plan: the sheet prints one apartment total, not per-room areas"
        ],
    ),
    "high_quality_architectural-1575": _hr(
        status="scaled",
        m_per_unit=0.01418,
        evidence=["printed_areas"],
        source="6 of 9 printed room areas agree within 2% (WC 2,7 ET 15,0 ARKIET 4,0 VAR 8,5 VAR 8,4 KH 3,1 m2; also MH 12,2 PH 5,5 WC 2,5 TEKN 6,7 KHH 10,8 within 5%) = 0.01418; doors 0.01402 and SVG unit 0.01396 within 1.6%; dimension labels 9824, 4400, 2570, 2422, 4150 not measured; three plans on one sheet",
        printed=[
            ("WC", 2.7, None),
            ("ET", 15.0, None),
            ("ARKIET", 4.0, None),
            ("VAR", 8.5, None),
            ("KH", 3.1, None),
            ("PH", 5.5, None),
        ],
        notes=[
            "not used as per-room areas: OH/K 39.8 (two rooms in the gold), TV-AULA 20.3, MH1 10.6, MH2 11.8, MH3 12.1, KHH 10.8, TAKKAH 17.4, TEKN 6.7"
        ],
    ),
    "high_quality_architectural-2567": _hr(
        status="scaled",
        m_per_unit=0.02243,
        evidence=["printed_areas"],
        source="6 printed rooms matched by position agree within 1.5% (MH1 10,2 / 10,7, MH2 8,6, MH3 10,7, MH2 19,8, WC 2,1 m2) = 0.02243; SVG unit 0.02229 (-0.6%) and doors 0.02261 (+0.8%); dimension labels 5800, 9400, 13200 not measured",
        printed=[
            ("MH1", 10.2, (468 / 1412, 1396 / 1606)),
            ("MH1", 10.7, (922 / 1412, 1405 / 1606)),
            ("MH2", 8.6, (245 / 1412, 1396 / 1606)),
            ("MH3", 10.7, (928 / 1412, 720 / 1606)),
            ("MH2", 19.8, (929 / 1412, 512 / 1606)),
            ("WC", 2.1, (871 / 1412, 562 / 1606)),
        ],
        notes=[
            "the gold rooms have no labels and OH/K, ET, KPH, S, VH are merged or split differently from the print, so only these six printed areas are placed"
        ],
    ),
    "high_quality_architectural-3904": _hr(
        status="scaled",
        m_per_unit=0.0250,
        evidence=["dimension_lines"],
        source="bottom chain 4500/4500/3800 mm over 180/180/152 px (ticks at 727, 907, 1087, 1239) = 25.0, 25.0, 25.0 mm/px; SVG unit 0.02537 (+1.5%); no printed areas",
    ),
    "high_quality_architectural-5765": _hr(
        status="scaled",
        m_per_unit=0.02652,
        evidence=["printed_areas"],
        source="3 of 5 printed room areas of the right plan agree within 1% of their median (OH 19,5 MH 7,5 TK 2,0 m2; K 12,0 and MH 12,0 are 3% lower) = 0.02652; SVG unit 0.02674 (+0.8%) and doors 0.02625 (-1%); dimension labels 12200, 5600, 6600, 8300 not measured; text of the right plan is rotated",
        printed=[
            ("OH", 19.5, None),
            ("K", 12.0, None),
            ("MH", 7.5, None),
            ("MH", 12.0, None),
            ("TK", 2.0, None),
        ],
    ),
    "high_quality_architectural-6462": _hr(
        status="estimated",
        evidence=["printed_areas"],
        source="one printed area 'H+ALK+S 38,0 m2' for a combined room; OH + ALKOVI polygons are 19.3 m2 at the SVG unit, so it cannot be tied to a room pair and gives no scale (it would need 0.0142 m/px, 40% above the SVG unit and door check, which agree within 2%)",
        notes=[
            "sheet rotated 90 degrees; printed 'H+ALK+S 38,0 m2' not placed on a room"
        ],
    ),
    "high_quality_architectural-688": _hr(
        status="scaled",
        m_per_unit=0.00631,
        evidence=["dimension_lines"],
        source="left chain 2700/2250/1350/2100 = 8400 mm over 1331 px (ticks y=483, 910, 1266, 1474, 1814): 6.32, 6.31, 6.49, 6.18, total 6.31 mm/px; SVG unit 6.37 (+0.9%); same drawing as arch-11841 at higher resolution; no printed areas",
    ),
    "high_quality_architectural-843": _hr(
        status="scaled",
        m_per_unit=0.01437,
        evidence=["dimension_lines"],
        source="bottom chain 4800+4100 = 8900 mm over 619.5 px (ticks x=33, 367.5, 652.5): 14.35, 14.39, total 14.37 mm/px; left chain 3850+3850 gives 14.5-14.8; SVG unit 14.37; no printed areas",
    ),
}
# eval images (read the picture only; decision 0003): stem -> (status or None, evidence, notes)
EVAL_REVIEW_1 = {
    "high_quality-11553": {
        "status": "estimated",
        "m_per_unit": 0.027,
        "uncertainty": 0.15,
        "evidence": [],
        "source": "image only (scanned upside down, nothing printed): swing-door leaves 28-34 px against 0.80 m give about 0.027 m/px; the right-hand bedroom (about 100 x 147 px) at a typical 11.5 m2 gives 0.028; the house is 340 px = 9.2 m wide",
    },
    "high_quality-429": {
        "status": "estimated",
        "m_per_unit": 0.0173,
        "uncertainty": 0.15,
        "evidence": [],
        "source": "image only (hand-written room codes, nothing printed): door leaves 45-55 px against 0.80-0.90 m give about 0.0178; the top-right bedroom (155 x 265 px) at a typical 11.5 m2 gives 0.0167; the house is 555 px = 9.6 m wide",
    },
    "high_quality-9830": {
        "status": "not_to_scale",
        "m_per_unit": 0.0068,
        "uncertainty": 0.15,
        "evidence": ["not_to_scale_note"],
        "source": "the sheet says 'SUUNTAA ANTAVA, EI MITTAKAAVASSA.' (approximate, not to scale); eye estimate from the image: door leaves about 100-135 px against 0.80 m give 0.0068; the top-right bedroom at a typical 11.5 m2 gives 0.0070; the plan is about 1540 px = 10.5 m wide",
    },
    "high_quality_architectural-4828": {
        "status": "estimated",
        "m_per_unit": 0.0286,
        "uncertainty": 0.1,
        "evidence": ["printed_areas", "dimension_lines"],
        "source": "image only, three checks 12% apart so not scaled: the '3100' label across the 11,5 m2 bedroom (116 px) gives 0.0267; that room's printed 11,5 m2 against its inner box (116 x 117 px) gives 0.0291; the 09x21 door leaf (30 px) against 0.90 m gives 0.0300; mean 0.0286",
        "notes": [
            "printed per-room areas, two plans: LUKUTILA 11,5 OH 20,5 TYOH/VIERAS 14 R 9,5 WC 3,2 KHH 9,0 K 11,5 ET/AULA 13,5 LH 4,0 PH 4,5 TEKN 2,5 / MH 11,5 MH 11,5 KPH 7,0 VH 5,5 AULA/TV-TILA 27,5 MH 13,5 m2; dimension labels 4800 3700 3100 2550 1800 present"
        ],
    },
    "high_quality_architectural-8212": {
        "status": "estimated",
        "m_per_unit": 0.0185,
        "uncertainty": 0.15,
        "evidence": [],
        "source": "image only (only a lone '2700' dimension fragment): door leaves 35-50 px against 0.80 m give about 0.019; the living room (265 x 235 px) at a typical 20 m2 gives 0.018; the left plan is 485 px = 9.0 m wide",
    },
    "high_quality-3839": {
        "status": "estimated",
        "m_per_unit": 0.0285,
        "uncertainty": 0.2,
        "evidence": [],
        "source": "image only (room names, nothing printed; small two-storey cabin): door leaves about 28 px against 0.80 m give 0.0286; wall thickness about 7 px at 0.2 m gives 0.029; the house is 175 px = 5.0 m wide",
    },
    "high_quality-7073": {
        "status": "not_to_scale",
        "m_per_unit": 0.026,
        "uncertainty": 0.2,
        "evidence": ["not_to_scale_note"],
        "source": "the sheet says 'Ohjeellinen, ei mittakaavassa' (indicative, not to scale); eye estimate from the image: door leaves about 28 px against 0.80 m give 0.0286; a typical 12 m2 bedroom (150 x 145 px) gives 0.0235; the right plan is 380 px = 9.9 m wide at 0.026",
    },
    "high_quality_architectural-9909": {
        "status": "estimated",
        "m_per_unit": 0.0123,
        "uncertainty": 0.15,
        "evidence": [],
        "source": "image only (rotated 90 degrees, a black block hides part of the plan, no dimensions or areas): door leaf about 65 px against 0.80 m gives 0.0123; the MH bedroom (265 x 245 px) then has 9.8 m2, typical",
    },
}
HAND_REVIEW_2: dict = {}  # review-2's side file, filled in main()


def poly_area(poly):
    n = len(poly)
    return 0.5 * abs(
        sum(
            poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
            for i in range(n)
        )
    )


def point_in(poly, x, y):
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def door_median_px(elements, W, H):
    """Median long side of the swing-door boxes, in Stoa PNG pixels, and how many doors."""
    w = []
    for e in elements:
        if e["class"] == "door" and e["attrs"]["source_class"].startswith("Door Swing"):
            b = e["box"]
            w.append(max((b[2] - b[0]) * W, (b[3] - b[1]) * H))
    w.sort()
    if len(w) < 2:
        return None, len(w)
    m = len(w) // 2
    return (w[m] if len(w) % 2 else (w[m - 1] + w[m]) / 2), len(w)


def finish_scale(stem, scale, ref, door_px, n_doors):
    """Every dev image gets a value: keep a measured scale (and add the two approximations as checks), else estimate."""
    door = DOOR_M / door_px if door_px else None
    checks = f"SVG unit {ref:.6f} m/px"
    if door:
        checks += f", doors {door:.6f} m/px ({n_doors} swing doors, median leaf at {DOOR_M} m; {100 * (door / ref - 1):+.1f}% vs SVG unit)"
    else:
        checks += f", doors n/a ({n_doors} swing doors)"
    if scale["status"] == "scaled":
        scale["source"] += " | approximations: " + checks
        scale.pop("reference_m_per_unit", None)  # the model keeps it off scaled
        return scale
    scale["reference_m_per_unit"] = round(ref, 7)
    agree = door is not None and abs(door / ref - 1) <= 0.10
    unc = 0.08 if agree else 0.15
    if scale["status"] == "no_scale":
        scale["status"] = "estimated"
    base = scale["source"]
    scale["m_per_unit"] = round(ref, 7)
    scale["uncertainty"] = unc
    scale["source"] = (
        f"best effort from the CubiCasa5K annotation unit (1 svg unit about 1 cm) and door width: {checks}; "
        + (
            "the two agree within 10%"
            if agree
            else "the two disagree or doors are missing: wider uncertainty"
        )
        + (
            f" | {base}"
            if base and not base.startswith(("not reviewed", "looked at", "scale not"))
            else ""
        )
    )
    return scale


def apply_areas(g, W, H, scale, printed):
    """area_m2 on every room with a polygon. printed: [(label, m2, near)] read from the sheet; matched to rooms."""
    mpp = scale["m_per_unit"]
    unc = {"scaled": 0.09}.get(scale["status"]) or round(
        2 * (scale.get("uncertainty") or 0.15) + 0.05, 2
    )
    src = "geometry_x_scale" if scale["status"] == "scaled" else "geometry_x_estimate"
    used = set()
    rooms = [r for r in g["rooms"] if r["polygon"]]
    for r in rooms:
        r["_a"] = poly_area(r["polygon"]) * W * H * mpp * mpp
        r.update(
            area_m2=round(r["_a"], 2),
            area_status="estimated",
            area_source=src,
            area_uncertainty=unc,
        )
    unmatched = []
    for label, val, near in printed:
        best = None
        if near:
            for r in rooms:
                if id(r) not in used and point_in(r["polygon"], near[0], near[1]):
                    best = r
                    break
        else:
            cands = [
                r for r in rooms if id(r) not in used and abs(r["_a"] / val - 1) <= 0.10
            ]
            same = [r for r in cands if (r["label"] or "").upper() == label.upper()]
            cands = same or [r for r in cands if abs(r["_a"] / val - 1) <= 0.06]
            if cands:
                best = min(cands, key=lambda r: abs(r["_a"] / val - 1))
        if best is None:
            unmatched.append(f"{label} {val}")
            continue
        used.add(id(best))
        best.update(
            area_m2=val,
            area_status="exact",
            area_source="printed",
            area_uncertainty=None,
        )
    for r in g["rooms"]:
        r.pop("_a", None)
    return len(used), unmatched


# ---------- geometry ----------
def mat_mul(a, b):  # a applied after b: a*b, matrices (a,b,c,d,e,f)
    return (
        a[0] * b[0] + a[2] * b[1],
        a[1] * b[0] + a[3] * b[1],
        a[0] * b[2] + a[2] * b[3],
        a[1] * b[2] + a[3] * b[3],
        a[0] * b[4] + a[2] * b[5] + a[4],
        a[1] * b[4] + a[3] * b[5] + a[5],
    )


def parse_transform(t: str | None):
    m = (1, 0, 0, 1, 0, 0)
    if not t:
        return m
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", t):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix":
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        else:
            continue
        m = mat_mul(m, n)
    return m


def apply(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def pts(s: str):
    v = [float(x) for x in re.split(r"[\s,]+", s.strip()) if x]
    return list(zip(v[0::2], v[1::2]))


def dedupe(poly):
    out = []
    for p in poly:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


# ---------- svg ----------
def svg_size(root):
    return float(root.get("width")), float(root.get("height"))


def own_polygon(g, prefer=("BoundaryPolygon",)):
    """Points (local coordinates) of the group's own outline polygon."""
    for child in g:
        if child.tag == NS + "polygon":
            return pts(child.get("points"))
    for child in g:
        if (
            child.tag == NS + "g"
            and (child.get("class") or "").split()[:1]
            and child.get("class").split()[0] in prefer
        ):
            for pg in child.iter(NS + "polygon"):
                return pts(pg.get("points"))
    return None


def local_points(
    g,
    m=(1, 0, 0, 1, 0, 0),
    skip=("Direction", "Name", "Dimension", "SelectionControls", "Visual"),
):
    """All outline points below g in g's local frame (polygons, rects, circles, lines, paths with absolute M/L coordinates)."""
    out = []
    for ch in g:
        cl = (ch.get("class") or "").split()[:1]
        if cl and cl[0] in skip:
            continue
        cm = mat_mul(m, parse_transform(ch.get("transform")))
        tag = ch.tag.replace(NS, "")
        if tag == "polygon" or tag == "polyline":
            out += [apply(cm, p) for p in pts(ch.get("points") or "")]
        elif tag == "rect":
            x, y, w, h = (float(ch.get(k) or 0) for k in ("x", "y", "width", "height"))
            out += [
                apply(cm, p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
            ]
        elif tag == "circle":
            cx, cy, r = (float(ch.get(k) or 0) for k in ("cx", "cy", "r"))
            out += [apply(cm, p) for p in ((cx - r, cy - r), (cx + r, cy + r))]
        elif tag == "line":
            out += [
                apply(cm, (float(ch.get("x1")), float(ch.get("y1")))),
                apply(cm, (float(ch.get("x2")), float(ch.get("y2")))),
            ]
        elif tag == "g":
            out += local_points(ch, cm, skip)
    return out


def hull_box(points):
    x0, y0, x1, y1 = bbox(points)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def walk(g, m, ctx, out):
    """Collect (class, matrix, element, floor) for every group below g."""
    for ch in g:
        if ch.tag != NS + "g":
            continue
        cm = mat_mul(m, parse_transform(ch.get("transform")))
        cl = ch.get("class") or ""
        floor = ctx
        if cl.startswith("Floorplan"):
            floor = ch.get("id") or cl.split()[-1]
        out.append((cl, cm, ch, floor))
        walk(ch, cm, floor, out)


def label_of(space):
    for e in space.iter(NS + "g"):
        if (e.get("class") or "") == "TextLabel NameLabel":
            t = next(e.iter(NS + "text"), None)
            return (t.text or "").strip() if t is not None else ""
    return ""


def room_type(cl: str, label: str):
    w = cl.split()[1:]
    k = w[0] if w else ""
    if k == "Bedroom":
        return "bedroom", False
    if k == "Kitchen":
        return "kitchen", False
    if k == "Bath":
        return ("wc" if re.match(r"\s*WC", label.upper()) else "bathroom"), False
    if k == "Sauna":
        return "sauna", False
    if k == "Outdoor":
        return ("balcony" if len(w) > 1 and w[1] == "Balcony" else "outdoor"), True
    if k in ("LivingRoom", "Dining", "Den", "RecreationRoom"):
        return "living", False
    if k in ("Entry", "Lobby", "DraughtLobby", "Hall", "Alcove"):
        return "hall", False
    if k in (
        "Storage",
        "Closet",
        "Utility",
        "DressingRoom",
        "Garage",
        "CarPort",
        "Attic",
        "Basement",
    ):
        return "storage", False
    return "other", False


def element_class(cl: str):
    if cl.startswith("Door ") or cl == "Door":
        return "door"
    if cl.startswith("Window"):
        return "window"
    if not cl.startswith("FixedFurniture "):
        return None
    k = cl[len("FixedFurniture ") :]
    if k == "Toilet":
        return "toilet"
    if "Sink" in k:
        return "sink"
    if k == "Shower":
        return "shower"
    if k.startswith("Bathtub"):
        return "bathtub"
    if "SaunaStove" in k:
        return "sauna_stove"
    return None


def storey_of(fid: str):
    """The SVG's own Floorplan id ("Floor-1", "Floor-2", "Basement-1"); a string, as extraction_v1 wants."""
    return fid or None


def build_dev(svg_bytes: bytes, file: str, W: int, H: int, ws: int, hs: int):
    """W,H = size of the Stoa PNG (F1_original); ws,hs = size of F1_scaled, the pixel frame of model.svg."""
    root = ET.fromstring(svg_bytes)

    def fr(p):
        return (
            min(1.0, max(0.0, p[0] / ws)),
            min(1.0, max(0.0, p[1] / hs)),
        )  # clamp: a few shapes poke out of the page

    items = []
    walk(root, (1, 0, 0, 1, 0, 0), None, items)
    floors = [(cl, m, e, f) for cl, m, e, f in items if cl.startswith("Floorplan")]
    plan_ids = {}
    plans = []
    for cl, m, e, f in floors:
        plan_ids[f] = f"p{len(plans) + 1}"
        plans.append(
            {
                "id": plan_ids[f],
                "page": 1,
                "box": None,
                "storey": storey_of(f),
                "_pts": [],
            }
        )
    elements, rooms = [], []
    merged = 0
    seen = {}
    for cl, m, e, f in items:
        if f is None:
            continue
        pid = plan_ids[f]
        pl = next(p for p in plans if p["id"] == pid)
        if cl.startswith("Space "):
            local = own_polygon(e)
            if not local:
                continue
            poly = [fr(apply(m, p)) for p in dedupe(local)]
            label = label_of(e)
            t, outdoor = room_type(cl, label)
            x0, y0, x1, y1 = bbox(poly)
            rooms.append(
                {
                    "id": f"r{len(rooms) + 1}",
                    "type": t,
                    "label": label,
                    "page": 1,
                    "plan": pid,
                    "polygon": [[round(a, 5), round(b, 5)] for a, b in poly]
                    if len(poly) >= 3
                    else None,
                    "box": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
                    "area_m2": None,
                    "apartment": None,
                    "outdoor": outdoor,
                    "attrs": {"source_class": cl},
                }
            )
            pl["_pts"] += poly
            continue
        if cl.startswith("Wall"):
            local = own_polygon(e)
            if local:
                pl["_pts"] += [fr(apply(m, p)) for p in local]
        ec = element_class(cl)
        if ec is None:
            continue
        local = own_polygon(e)
        if not local:
            lp = local_points(e)
            if not lp:
                continue
            local = hull_box(lp)
        raw = [apply(m, p) for p in dedupe(local)]
        poly = [fr(p) for p in raw]
        key = (
            ec,
            tuple((round(a, 2), round(b, 2)) for a, b in raw),
        )  # identical in the SVG, not after clamping
        if key in seen:
            merged += 1
            seen[key]["attrs"]["multiplicity"] = (
                seen[key]["attrs"].get("multiplicity", 1) + 1
            )
            continue
        x0, y0, x1, y1 = bbox(poly)
        seen[key] = el = {
            "id": f"e{len(elements) + 1}",
            "class": ec,
            "page": 1,
            "plan": pid,
            "box": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
            "polygon": [[round(a, 5), round(b, 5)] for a, b in poly]
            if len(poly) >= 3
            else None,
            "attrs": {"source_class": cl},
        }
        elements.append(el)
    for pl in plans:
        p = pl.pop("_pts")
        if p:
            x0, y0, x1, y1 = bbox(p)
            pl["box"] = [
                round(max(0, x0), 5),
                round(max(0, y0), 5),
                round(min(1, x1), 5),
                round(min(1, y1), 5),
            ]
        else:
            pl["box"] = [0.0, 0.0, 1.0, 1.0]
    notes = (
        [f"{merged} element(s) drawn twice at identical geometry merged"]
        if merged
        else []
    )
    stem = Path(file).stem
    scale, snotes = make_scale(stem, ws, W)
    notes += [n for n in snotes if n != "scale not reviewed"]
    door_px, n_doors = door_median_px(elements, W, H)
    scale = finish_scale(stem, scale, SVG_M_PER_UNIT * ws / W, door_px, n_doors)
    printed = [(a, b, None) for a, b in PRINTED.get(stem, [])]
    hr = HAND_REVIEW_1.get(stem) or HAND_REVIEW_2.get(stem)
    if hr:
        printed = [
            (p[0], p[1], p[2] if len(p) > 2 else None) for p in hr.get("printed", [])
        ]
        notes += list(hr.get("notes", []))
    g = {
        "schema": "extraction_v1",
        "file": file,
        "split": "dev",
        "truth": "elements",
        "pages": [{"page": 1, "width": W, "height": H, "unit": "px"}],
        "scale": scale,
        "plans": plans,
        "elements": elements,
        "rooms": rooms,
        "apartments": [],
        "counts": None,
        "notes": notes,
    }
    if hr and hr.get("status"):
        scale = apply_hand_review(scale, hr, SVG_M_PER_UNIT * ws / W)
        g["scale"] = scale
    n_ex, unmatched = apply_areas(g, W, H, scale, printed)
    if printed:
        notes.append(
            f"printed room areas matched to rooms: {n_ex} of {len(printed)}"
            + (f" (not matched: {', '.join(unmatched)})" if unmatched else "")
        )
    return g


def apply_hand_review(scale, hr, ref):
    """A hand review (images read in full) replaces the automatic scale."""
    st = hr["status"]
    out = {
        "status": st,
        "m_per_unit": hr.get("m_per_unit"),
        "evidence": hr.get("evidence", []),
        "text": hr.get("text"),
        "source": "hand review: " + hr.get("source", "; ".join(hr.get("checks", []))),
    }
    if st != "scaled":
        out["reference_m_per_unit"] = round(ref, 7)
    if hr.get("uncertainty"):
        out["uncertainty"] = hr["uncertainty"]
    if (
        out["m_per_unit"] is None
    ):  # no value from the sheet: keep the best effort one, with the reviewed status
        if st in ("not_to_scale", "estimated"):
            scale["status"] = st
            scale["evidence"] = hr.get("evidence", scale.get("evidence", []))
            scale["source"] = out["source"] + " | " + scale["source"]
        return scale
    return out


# Frame (checked on 60 dev plans, see review-1.md section 8): model.svg user units are pixels of F1_scaled.png
# (origin top left, uniform), so fraction = svg coordinate / F1_scaled size; F1_original (= the Stoa PNG) has the same aspect.
def png_size(path: Path):
    with open(path, "rb") as f:
        b = f.read(24)
    return struct.unpack(">II", b[16:24])


def template_of(q: str):
    for pre, k in TEMPLATES.items():
        if q.startswith(pre):
            return k
    return None


def counts_from_gold(g: dict):
    """The dataset's counting rules, applied to a dev gold file (rule check)."""
    c = collections.Counter()
    for e in g["elements"]:
        c[e["class"]] += e["attrs"].get(
            "multiplicity", 1
        )  # duplicates count as drawn objects (the dataset counts them)
    r = collections.Counter(x["type"] for x in g["rooms"])
    sauna = r["sauna"] or c["sauna_stove"]
    return {
        "windows": c["window"],
        "floors": len(g["plans"]),
        "wc_seats": c["toilet"],
        "sinks": c["sink"],
        "showers_baths": c["shower"] + c["bathtub"],
        "doors": c["door"],
        "saunas": sauna,
        "kitchens": r["kitchen"],
        "bedrooms": r["bedroom"],
        "bathrooms": r["bathroom"],
        "wc_rooms": r["wc"],
        "balconies": r["balcony"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zip", default="data/external/cubicasa5k/cubicasa5k.zip")
    ap.add_argument("--check", action="store_true")
    ap.add_argument(
        "--dim-lines",
        default="data/stoa/extraction_gold/_scale/cubicasa_dimension_lines.json",
        help="review-2 dimension-line scale cases ([{file, m_per_unit, checks, note}]); read if present",
    )
    ap.add_argument(
        "--hand-review-2",
        default="data/stoa/extraction_gold/_scale/cubicasa_hand_review_2.json",
        help="review-2 hand reviews ({file: {...}} or [{file, ...}]); read if present",
    )
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    ds, out = Path(a.dataset), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    split_of = {}
    for sp in ("dev", "eval"):
        for line in (Path(a.split) / f"{sp}.jsonl").read_text("utf8").splitlines():
            d = json.loads(line)
            if "cubicasa5k" in d["path"]:
                split_of.setdefault(d["path"], sp)
    qs = collections.defaultdict(dict)  # path -> template -> (id, answer)
    for i, line in enumerate(
        (ds / "questions.jsonl").read_text("utf8").splitlines(), 1
    ):
        d = json.loads(line)
        if "cubicasa5k" not in d["path"]:
            continue
        t = template_of(d["question"])
        if t:
            qs[d["path"]][t] = (i, d["answer"])
    z = zipfile.ZipFile(a.zip)
    dl = Path(a.dim_lines)
    if dl.exists():
        for c in json.loads(dl.read_text("utf8")):
            DIM_LINES[Path(c["file"]).stem] = c
    hr2 = Path(a.hand_review_2)
    if hr2.exists():
        raw = json.loads(hr2.read_text("utf8"))
        items = raw.items() if isinstance(raw, dict) else ((c["file"], c) for c in raw)
        for f, c in items:
            c = dict(c)
            c["printed"] = [
                (x["label"], x["area_m2"], x.get("near"))
                for x in c.pop("printed_room_areas", [])
            ]
            if c.get("notes") and isinstance(c["notes"], str):
                c["notes"] = [c["notes"]]
            kinds = {
                "printed_room_areas": "printed_areas",
                "dimension_lines": "dimension_lines",
                "scale_text": "scale_text",
                "scale_bar": "scale_bar",
                "printed_areas": "printed_areas",
                "not_to_scale_note": "not_to_scale_note",
            }
            c["evidence"] = [
                kinds[k] for k in dict.fromkeys(c.get("evidence") or []) if k in kinds
            ]
            if c.get("text") and not re.fullmatch(r"1:\d+", c["text"].strip()):
                c["source"] = c["text"] + (
                    " | " + "; ".join(c.get("checks") or []) if c.get("checks") else ""
                )
                c["text"] = None
            elif c.get("checks"):
                c["source"] = "; ".join(c["checks"])
            if (
                c.get("status") == "not_to_scale"
                and "not_to_scale_note" not in c["evidence"]
            ):
                c["evidence"].append("not_to_scale_note")
            HAND_REVIEW_2[Path(f).stem] = c
    n = collections.Counter()
    avg = collections.Counter()
    results = collections.defaultdict(lambda: [0, 0, []])
    for path in sorted(qs):
        sp = split_of.get(path)
        if sp is None:
            continue
        if a.limit and sum(n.values()) >= a.limit:
            break
        stem = Path(path).stem
        W, H = png_size(ds / path)
        if sp == "dev":
            cat, num = stem.rsplit("-", 1)
            ws, hs = struct.unpack(
                ">II", z.read(f"cubicasa5k/{cat}/{num}/F1_scaled.png")[16:24]
            )
            g = build_dev(
                z.read(f"cubicasa5k/{cat}/{num}/model.svg"), path, W, H, ws, hs
            )
            avg["elements"] += len(g["elements"])
            avg["rooms"] += len(g["rooms"])
            if a.check:
                got = counts_from_gold(g)
                for t, (qid, ans) in qs[path].items():
                    r = results[t]
                    r[1] += 1
                    if got[t] == ans:
                        r[0] += 1
                    else:
                        r[2].append((qid, path, ans, got[t]))
        else:
            counts = {}
            for t, (qid, ans) in qs[path].items():
                counts[COUNT_KEY[t]] = ans
            g = {
                "schema": "extraction_v1",
                "file": path,
                "split": "eval",
                "truth": "counts",
                "pages": [{"page": 1, "width": W, "height": H, "unit": "px"}],
                "scale": {
                    "status": "no_scale",
                    "m_per_unit": None,
                    "evidence": [],
                    "text": None,
                    "source": "eval split: not labelled",
                },
                "plans": [],
                "elements": [],
                "rooms": [],
                "apartments": [],
                "counts": counts,
                "notes": [
                    "scale not reviewed",
                    (
                        "counts from question answers; showers_baths is one combined count under"
                        " 'shower'; room:sauna is the sauna count (room else stove)"
                    ),
                ],
            }
            rv = EVAL_REVIEW_1.get(stem)
            r2 = HAND_REVIEW_2.get(stem)
            if r2 and r2.get("status") == "scaled" and r2.get("m_per_unit"):
                rv = {
                    "status": "scaled",
                    "m_per_unit": r2["m_per_unit"],
                    "evidence": [e for e in r2["evidence"] if e != "not_to_scale_note"],
                    "source": r2.get("source") or "",
                }
            if rv:
                g["scale"] = {
                    "status": rv["status"],
                    "m_per_unit": rv["m_per_unit"],
                    "evidence": rv["evidence"],
                    "text": None,
                    "source": "hand review of the image (eval: image only, no SVG): "
                    + rv["source"],
                }
                if rv.get("uncertainty"):
                    g["scale"]["uncertainty"] = rv["uncertainty"]
                g["notes"].remove("scale not reviewed")
                g["notes"] += rv.get("notes", [])
            if r2:
                pa = ", ".join(f"{a} {b}" for a, b, _ in r2["printed"])
                if pa:
                    g["notes"].append(f"printed areas (review-2): {pa}")
                g["notes"] += list(r2.get("notes") or [])
        (out / f"{stem}.json").write_text(
            json.dumps(g, ensure_ascii=False), encoding="utf8"
        )
        n[sp] += 1
    print(f"written: dev {n['dev']}, eval {n['eval']} -> {out}")
    if n["dev"]:
        print(
            f"dev mean per file: elements {avg['elements'] / n['dev']:.1f}, rooms {avg['rooms'] / n['dev']:.1f}"
        )
    if a.check:
        print("rule check (dev):")
        for t in TEMPLATES.values():
            ok, tot, miss = results[t]
            print(f"  {t}: {ok}/{tot}")
            for m in miss[:20]:
                print(f"     miss id {m[0]} {m[1]} answer {m[2]} gold {m[3]}")
            if len(miss) > 20:
                print(f"     ... {len(miss) - 20} more")


if __name__ == "__main__":
    sys.exit(main())
