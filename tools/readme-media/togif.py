#!/usr/bin/env python3
"""Turns a recording (lib.cjs: PNG frames and frames.json) into a GIF with ffmpeg.

    python3 tools/readme-media/togif.py <frames dir> <out.gif> [--width 1200] [--fps 12] [--cap 4]

A frame stays on screen until the next one was taken, divided by the speed it was recorded at, and
never longer than --cap seconds. One palette for the whole GIF, no dithering: flat interface
colours stay flat, and the file stays small.
"""

import argparse
import itertools
import json
import subprocess
from pathlib import Path


def durations(frames: list[dict], cap: float) -> list[tuple[str, float]]:
    """(frame file, seconds on screen) per frame; the last entry of `frames` only ends the one before."""
    return [
        (a["name"], min((b["t"] - a["t"]) / 1000 / a["speed"], cap))
        for a, b in itertools.pairwise(frames)
    ]


def concat_list(folder: Path, shown: list[tuple[str, float]]) -> str:
    """ffmpeg's concat list; the last file is named twice, as the demuxer needs for its duration."""
    lines = []
    for name, seconds in shown:
        lines += [f"file '{(folder / name).as_posix()}'", f"duration {seconds:.4f}"]
    lines.append(f"file '{(folder / shown[-1][0]).as_posix()}'")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("frames", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--cap", type=float, default=4.0)
    parser.add_argument("--colors", type=int, default=256)
    args = parser.parse_args()
    folder = args.frames.resolve()
    shown = durations(json.loads((folder / "frames.json").read_text()), args.cap)
    (folder / "list.txt").write_text(concat_list(folder, shown))
    look = (
        f"fps={args.fps},scale={args.width}:-1:flags=lanczos,split[a][b];"
        f"[a]palettegen=max_colors={args.colors}:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(folder / "list.txt"), "-vf", look, "-loop", "0", str(args.out)],
        check=True,
    )  # fmt: skip
    seconds = sum(s for _, s in shown)
    print(
        f"{args.out}: {seconds:.1f} s, {args.out.stat().st_size / 1e6:.2f} MB, {len(shown)} frames"
    )


if __name__ == "__main__":
    main()
