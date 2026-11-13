# 02-reference/raw-data: unprocessed inputs

Collected 2026-11-10 with yt-dlp 2026.10.26. Kept so the curated files can be checked or rebuilt. Don't edit; derive new files instead.

| File | What it is | Used for |
|---|---|---|
| `video-metadata.jsonl` | One JSON object per video (93): id, url, title, channel, duration, upload date, view count, first 500 characters of the description. Covers every catalogued team video plus the key official ones | `../junction-videos.md` (placements, partners, durations) |
| `youtube-search-results.tsv` | Every hit from about 50 YouTube searches (484 rows, **unfiltered**: includes unrelated "junction" videos) | Finding candidates for `../junction-videos.md` |
| `captions-vtt/*.en.vtt` | YouTube auto-generated English captions, as downloaded, for the 9 analysed pitches | Source of `../pitch-transcripts/` |

The derived files are in `02-reference/`: `junction-videos.md`, `junction-channel-index.md`, `pitch-transcripts/`, `pitch-frames/`, `pitch-analysis.md`, `pitch-breakdown.csv`, `jury-questions.csv`.

Contact sheets in `../pitch-frames/` were built from YouTube storyboard thumbnails (sb0, 320×180, a 3×3 grid per image), sampling every 3rd frame (stage pitches) or every 5th (2-minute videos). The original storyboard images were not kept; they can be re-downloaded with `yt-dlp -j <url>` (format `sb0` fragments).
