# Omni takes

One entry per take, newest first. Media in `media/takes/<id>/` (gitignored); prompts in
`script/prompts/`.

Transcribe a take's dialogue:

```bash
ffmpeg -v error -y -i media/takes/<id>/take.mp4 -ar 16000 -ac 1 /tmp/a.wav
uvx --python 3.12 --from faster-whisper --with numpy python -I -c "
import wave,numpy as np; from faster_whisper import WhisperModel
w=wave.open('/tmp/a.wav'); a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
[print(f'{s.start:.1f}-{s.end:.1f} {s.text}') for s in WhisperModel('small',device='cpu',compute_type='int8').transcribe(a)[0]]"
```

## 001 (2026-11-14, gemini-omni-1.2-flash, prompt `s02_smash_v1.txt`)

- Input: last frame of the first test clip (`media/source/s01_last_frame.png`), 720x1280.
- Output: 8.0 s, 720x1280, 24 fps, audio. 33 s to generate, 46,336 video output tokens.
- Seam: first frame matches the real last frame (checked side by side).
- Action: he has the sledgehammer almost at once (picked up off screen, not shown), swings at the wall
  below the TV, plaster cracks, dust cloud, then a white panel door with rough plaster edges and
  debris on the floor; thumbs up. The camera moves closer for the reveal (reads as a cut).
- Audio (transcribed): "I'm just going to pick up the hammer and boom!" 0.0-4.0, "Done!" 7.0-8.0.
  Voice match with the real footage not checked yet.
- Verdict: keep as the v1 smash. Redo if we want the hammer pick-up visible.
- Used in `media/renders/promo_v1.mp4` (real clip + take 001, 20.8 s).
