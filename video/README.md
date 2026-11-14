# Promo video

A short, funny vertical promo for our Stoa product: a guy wants a door where there is a wall, checks
the app, the app approves (not load-bearing, no pipes, building code OK, with the drawing and page it
read), he smashes the wall and a door appears. Real phone footage blended with AI-generated shots,
then edited in HyperFrames. Started 2026-11-14 (Bogdan).

## Who does what (Bogdan, 2026-11-14)

- **Bogdan** films the real footage and picks between the final takes.
- **Claude** writes the detailed script for every scene ([script/SCRIPT.md](script/SCRIPT.md)) and
  the Omni prompts, generates the AI shots, checks each Omni result in detail (checklist below), cuts
  everything together, then edits further in HyperFrames (titles, app UI overlay, sound, music).

## Layout

| Path | Tracked | What |
| --- | --- | --- |
| `script/SCRIPT.md` | yes | Scene-by-scene script: beats, dialogue, real vs AI, overlays, sound, timing. |
| `script/RESEARCH.md` | yes | Facts the video may claim, with sources (Finnish sauna and wall rules, promo craft, Stoa). |
| `script/prompts/` | yes | One prompt file per AI shot and version (`s02_smash_v1.txt`, ...). |
| `tools/omni.py` | yes | Generates one take with Gemini Omni, saves it with its prompt, inputs and usage. |
| `media/source/` | no | Real footage and frames cut from it. |
| `media/takes/<id>/` | no | One folder per Omni take: `take.mp4`, `prompt.txt`, inputs, `meta.json`. |
| `media/takes/log.jsonl` | no | One line per take: model, prompt file, seconds, tokens. |
| `media/renders/` | no | Cuts and final renders. |
| `edit/` | yes, once made | The HyperFrames project (HTML composition). Media only by path into `media/`. |

`media/` is gitignored: the footage shows our faces and the repo is public. Back it up before
Sunday 15 Nov; nothing in it is on GitHub.

## How the AI shots are made

1. Film the real part on the phone camera (not WhatsApp: it compresses to 478x850). Hold the phone
   still and end each real shot on the frame the AI shot should start from (hammer raised, wall in view).
2. Cut that last frame: `ffmpeg -sseof -0.2 -i <clip> -frames:v 1 -update 1 media/source/<name>.png`.
   Inputs need at least 700 px on the short side; upscale with
   `-vf scale=720:1280:flags=lanczos` if needed.
3. Write the prompt in `script/prompts/`, then generate one take:
   ```bash
   set -a && . ./.env && set +a
   python3 -I video/tools/omni.py --take 002 --image video/media/source/s01_last_frame.png \
       --prompt-file video/script/prompts/s02_smash_v1.txt
   ```
4. Check the take (below), log the verdict in [TAKES.md](TAKES.md), adjust the prompt as a new
   version, repeat. Pilot one take per prompt before making several.

### The API

- Key: `GEMINI_API_KEY` in the repo's gitignored `.env`, from the hackathon's temporary Google account
  (goo.gle/hackathon-account). That account and key are deleted the day after the event. Never put
  the key in code, docs, the board or chat.
- Model: `gemini-omni-1.2-flash` (newest Omni on the key; `gemini-omni-1.1-flash` and
  `gemini-omni-flash-preview` exist too). Omni works only through the **Interactions API**
  (`POST /v1beta/interactions` with `response_modalities: ["video"]`); `generateContent` refuses it.
  No Veo models are on this key (checked 2026-11-14).
- Output (take 001): 8.0 s, 720x1280, 24 fps, with generated audio and dialogue, about 33 s per call,
  about 46k video output tokens. Price per token unknown: check aistudio.google.com/spend.
- Not abuse: the organisers watch usage. Stay around 10-20 takes in total.
- Untested: video as input (editing real footage directly). Images as input work.

## Checking every Omni take

Pull frames and look at them, every time (`ffmpeg -i take.mp4 -vf "fps=2,scale=240:-1,tile=8x2"
-frames:v 1 sheet.jpg`), plus a full-size frame at each key moment.

- **Seam:** first generated frame vs the real last frame side by side. Same room, light, angle,
  person, clothes, objects on the table.
- **Identity:** face, hair, t-shirt print, shorts, watch stay the same through the shot.
- **Action:** every beat in the prompt happens, in order, nothing extra (props popping in, extra
  people, cuts we didn't ask for).
- **Physics and artefacts:** hands and fingers, hammer grip, debris and dust behave, no morphing
  door, no melting objects, the wall and door line up with the room.
- **Audio:** transcribe the dialogue (faster-whisper, see TAKES.md) and compare with the script;
  listen for voice match with the real footage; sound effects on time.
- **Text:** no garbled text in the frame (we add all text in the edit).
- **Verdict** in TAKES.md: keep, keep a range (`2.5-6.0 s`), or redo with the prompt change.

## Editing

- Rough cut with ffmpeg (concat, trim), then HyperFrames (`npx hyperframes@0.9.43`, HTML
  compositions rendered to MP4) for the app UI overlay on the phone, "Approved" stamp, captions, end
  card, sound effects and music. Useful commands: `init`, `preview`, `render`, `snapshot` (check key
  frames), `audio`/`beats` (sync to sound), `check`.
- Do not use `hyperframes publish` or `share`: they upload the project, and our faces stay off public URLs.
- Music and voice can come from the same key (Lyria, TTS) if needed.
- Final: 9:16, 1080x1920 if the sources allow, about 20-30 s, loudness normalized.

## Gotchas

- 2026-11-14: Kling refuses inputs under 700 px on the short side; WhatsApp video is 478x850, so
  upscale or use the original file.
- 2026-11-14: Omni returns the video inside `steps`, not `outputs`; `omni.py` searches the whole
  response for media.
- 2026-11-14: the prompt must name the target wall ("blank white wall on the right, below the TV, not
  the existing doorway"), or the model may hit the existing door.
