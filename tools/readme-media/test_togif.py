"""togif.py: how long each recorded frame stays on screen, and the list ffmpeg reads."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("togif", Path(__file__).with_name("togif.py"))
togif = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(togif)

FRAMES = [
    {"name": "00001.png", "t": 1000, "speed": 1},
    # recorded during a wait that plays 4 times faster
    {"name": "00002.png", "t": 1500, "speed": 4},
    {"name": "00003.png", "t": 3500, "speed": 1},
    # the end mark lib.cjs writes: only a time
    {"name": None, "t": 13500, "speed": 1},
]


def test_a_frame_lasts_until_the_next_one_divided_by_its_speed_and_capped():
    assert togif.durations(FRAMES, cap=4.0) == [
        ("00001.png", 0.5),
        ("00002.png", 0.5),  # 2 s at speed 4
        ("00003.png", 4.0),  # 10 s, capped
    ]


def test_the_concat_list_names_the_last_frame_twice(tmp_path):
    listing = togif.concat_list(tmp_path, [("00001.png", 0.5), ("00002.png", 1.25)])
    assert listing.splitlines() == [
        f"file '{tmp_path.as_posix()}/00001.png'",
        "duration 0.5000",
        f"file '{tmp_path.as_posix()}/00002.png'",
        "duration 1.2500",
        f"file '{tmp_path.as_posix()}/00002.png'",
    ]
