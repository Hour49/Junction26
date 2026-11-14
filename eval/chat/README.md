# Chat harness

Measures the project chat the way a judge uses it: multi-turn scripts (a question, then "are you
sure?", "show me", "and the kitchen?") against a running backend, scored per turn. Use it to get a
baseline and to A/B a chat change against it.

| File | What it does |
| --- | --- |
| `run.py` | Sends each script's turns to `POST /api/projects/{pid}/chat` (one chat per script, `chat_id` carried) or `/ask`, and writes one JSON line per turn |
| `score.py` | Scores runs side by side, records a numbers-only row in `eval/results/chat/`, checks a pre-registered A/B line |
| `replay.py` | An OpenAI-compatible proxy for the backend's `AGENT_BASE_URL` that records the model's replies and replays them, so a repeated call costs 0 USD |
| `walk.mjs` | The same messages typed into the web UI, with screenshots |

The set (`scripts.json`: messages, truths, words a reply must mention) and the project ids
(`ids.json`) live in `data/stoa/chat-eval/` (gitignored): the truths come from Stoa's drawings. So
do the runs and the replay cache, which hold drawing text. Only scores are committed.

## Metrics

Per turn: **right** (a truth is given: the card's value, else the first number in the text, equals
it or lies in its range; `"refuse"`: the turn refused), **answered** first turns and follow-ups,
**on topic** (the reply names the subject), **grounded** (every number in the text is backed by a
value in the chat's stored tool results, the reply or the message: a whole number by an equal
value, a decimal by one that rounds to it at its places, a number inside a string such as a room
label only as written; ids, boxes, polygons, pages, timings and cost don't count; needs
`--chats <env>/data/projects`; the stored file holds the whole chat, so a later turn's result can
back an earlier turn),
**level kept** (on a turn asking whether the chat is sure: the level the reply claims, named as
its confidence or by "yes"/"I'm sure" (high) or "not sure" (below high), is the level of the card
it was asked about) and **level changed** (that turn brings a card at another level),
**refusal offers**, **steps shown**, **view shown** (the turn puts a plan on screen), **http
errors**, **latency** p50 and max, **USD** per turn and in total.

## Run it

Commands from `eval/`. A backend with the projects of `ids.json`, e.g. a frozen env
(`tools/qa-env.sh <commit> 8894` with the projects copied into its `data/projects`).

```bash
D=../data/stoa/chat-eval
# 1. the model through the proxy: record pays for misses and stores them; replay never pays
python3 -m chat.replay --cache $D/replay --mode record    # prints its port
CHAT_MODEL=gemini AGENT_BASE_URL=http://127.0.0.1:<port> tools/qa-env.sh <commit> 8894
# 2. the scripts (--only s1-doors,... for a subset; the cap counts recorded cost)
python3 -m chat.run --base http://127.0.0.1:8894 --out $D/runs/<name>.jsonl --usd-cap 1.5
# 3. scores, side by side, and a committed row for a baseline
python3 -m chat.score $D/runs/a.jsonl $D/runs/b.jsonl --chats <env>/data/projects
python3 -m chat.score $D/runs/<name>.jsonl --chats ... --record <name> --commit <sha> --note "..."
# 4. an A/B: write the line first (right and grounded hold, the change's metric goes up)
python3 -m chat.score $D/runs/base.jsonl $D/runs/new.jsonl --chats ... --ab "view shown"
```

Replay serves a call only when its body is exactly one it has seen: the same build with the same
data replays the whole run at 0 USD (a frontend-only change, a scorer change, a re-check), and a
backend change replays every model step up to the first one whose prompt it changed, then pays
from there (`record`) or fails that turn with a 503 (`replay`). A replayed turn reports the cost
it had when recorded, so the backend's own `GEMINI_BUDGET_USD` counts it: start a replay env with a
budget well over the run's recorded cost (the proxy cannot spend in `replay` mode). `GET /stats`
on the proxy says how many calls were served from the cache, and a miss's body is kept in
`<cache>/misses/` to diff against the recorded call. The key blanks the `latency_s` timings the
backend puts in tool results; after a change to the key, `--rekey` renames the cache.

Checked 2026-11-14 on main 11a089e: the full set recorded (64 turns, 1.245 USD), then replayed:
64/64 replies word for word the same, 176 calls from the cache, 0 misses, 0 USD. Grounded on that
baseline: 64/64; with every standalone whole number in the replies raised by 1, it fails 22 of the
31 turns that have one (the rest land on another value the chat's tool results hold).

Model answers vary run to run, so a live A/B arm that matters gets two runs. A reply that is not
JSON (a streamed event body) is passed on but not recorded, so a streaming model call cannot be
replayed yet. `run.py` refuses an `--out` file that already has turns (a second run in it would
count every turn twice). `score.py --ab` guards level kept too when both runs have such turns,
and refuses two runs that do not cover the same turns: compare a subset with the same `--only`
on both.
