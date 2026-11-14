#!/usr/bin/env bash
# A contact sheet of a GIF, to check it frame by frame: sheet.sh <gif> <out.png> [seconds between frames] [columns]
set -euo pipefail
[[ $# -ge 2 ]] || { echo "usage: sheet.sh <gif> <out.png> [seconds between frames] [columns]" >&2; exit 2; }
ffmpeg -y -loglevel error -i "$1" -vf "fps=1/${3:-2.5},scale=600:-1,tile=${4:-3}x4" -frames:v 1 "$2"
