# What winning Junction pitches do: analysis of 9 pitch videos

Analysed 2026-11-10. Covers the five Junction 2025 top-5 stage pitches, the 2025 winners' two 2-minute submission videos, and two pitches from the Junction x Aalto Defence Hackathon (May 2026, a side event).

**Data behind this file**

| File | What it holds |
|---|---|
| [pitch-breakdown.csv](pitch-breakdown.csv) | One row per pitch (9): placement, partner, lengths, speakers, opening, numbers used, demo mode, slide style, call to action, failures, links |
| [jury-questions.csv](jury-questions.csv) | One row per jury question (17), with timestamp, category and answer summary |
| [pitch-transcripts/](pitch-transcripts/) | Cleaned transcripts of all 9 videos |
| [pitch-frames/](pitch-frames/) | One contact sheet per 2025 video (7): about 36 timestamped frames showing what was on screen |
| [raw-data/](raw-data/) | Original caption files, video metadata, raw search results |

**Method.** Speech comes from YouTube auto-captions (`raw-data/captions-vtt/`), de-duplicated into the transcripts. Visuals come from YouTube storyboard thumbnails (one frame every ~5 s for stage pitches, every 1 s for the 2-minute videos) assembled into the contact sheets. No video was watched at full resolution, so small on-screen text was not readable. Timings are approximate (±10 s), read from caption timestamps and frames. The two Defence videos end before any Q&A and have no frames.

**Note on "mentor questions".** None of these videos records mentor sessions. The questions below come from the **stage jury after each pitch**.

---

## 1. What the 2025 top 5 have in common

1. **Something real ran in front of the jury.** 3 of 5 demoed live (Wavelet, LoreDash, DroneStalker). The other two showed screenshots or video of a working build, and Walkthrough also built a mock store in the venue.
2. **The partner's challenge is named in the first 30 seconds**, usually with a thank-you to the partner by name.
3. **One big visual "wow".** GPU radio simulation over Hong Kong; a game generated live with music changing; a whole pitch inside a game-like app.
4. **Real technical depth, in plain words.** "Maxwell's equations, pure C++, OpenGL". "Beat every model in the dataset paper by 50% with a 300k-parameter LSTM". "MILP optimisation, then AI explains the decision".
5. **Humour and personality.** "Why? Cuz we're insane." An AI "Commander" roasting the team. "Which number is bigger, 90 or 10?"
6. **A way to try it.** QR code kept on screen through Q&A (LoreDash, λpump), a live link (DroneStalker), the mock store (Walkthrough).

**Observation.** The top two (Wavelet 1st, LoreDash 2nd) had almost no business case: live wow + real tech + fun won. The 2026 jury explicitly asks for "a problem worth solving" (junction-info §0), so keep one problem number anyway. λpump and Walkthrough show how to do it.

## 2. The basic structure (5-minute hard limit, then 2–4 min jury Q&A)

| Step | Time | Examples |
|---|---|---|
| 1. Hook | 0:00–0:30 | "Right now, beneath our feet…" (λpump). "No one likes grocery stores" (Walkthrough). Wikipedia's Random article button (LoreDash) |
| 2. Problem with a number or a persona | to ~1:30 | λpump's stick-figure operator "Jamie" + "500+ households", "$100k+". Walkthrough: 1.5–2 h/week, under 10% online |
| 3. The challenge and why we picked it | short | "hard problems, educational, cool tech" (Wavelet) |
| 4. Solution and demo | ~2 min, the core | Live demo or UI walkthrough |
| 5. How it works | 30–60 s | One tech-stack slide or diagram |
| 6. Impact, scale, next steps | 30 s | "Valmet → HSY Espoo → Finland → Europe" (λpump) |
| 7. Close and call to action | 10 s | QR or URL, thank you |

The tech-first teams (Wavelet, DroneStalker) skipped step 2. Every pitch hit the 5-minute wall: Walkthrough was cut with "Time's up", and DroneStalker said "we're only meant to have five minutes". Per-pitch lengths are in `pitch-breakdown.csv`: pitch 4:50–5:30, Q&A 2:15–4:00.

## 3. Jury questions (17 asked, 5 pitches)

| Question type | Count | Asked of |
|---|---|---|
| **Who did what, and how did you split the work?** | 3 | Wavelet, Walkthrough, λpump |
| **Is it real? Built this weekend? Live or recorded?** | 4 | Walkthrough ×2, LoreDash, λpump |
| **Technical choices: which models, framework, stack, and why** | 5 | LoreDash, DroneStalker ×2, λpump ×2 (one λpump question is also counted above) |
| **Real-world use / next 48 hours** | 2 | Wavelet |
| **Deployment constraints** | 1 | DroneStalker (on-device vs cloud in a war scenario) |
| **Partner/business objection** | 1 | Walkthrough ("store owners won't like this") |
| **Why this problem? Hardest part?** | 2 | λpump, LoreDash |

Lesson: Walkthrough opened with aspirational AR-glasses footage and admitted "that was not exactly our product". The jury then spent most of the Q&A on what was really built. Label concept footage clearly.

## 4. How the application was shown

| Team | Slides | Product |
|---|---|---|
| **Wavelet** (1st) | Plain white slides: equations, render screenshots | About 2 min of live laptop demo, fullscreen. A slow GPU start still got applause |
| **LoreDash** (2nd) | Deck styled exactly like the product: pixel art, gothic font, dark green | Game screenshots, then live generation with dynamic music. QR + URL on screen through Q&A |
| **DroneStalker** | No separate deck; the product is the deck | Tabbed app (camera feed / tracking / prediction) driven by a talking AI "Commander", then a model-performance chart. "Appendix: tech stack" slide ready for questions |
| **Walkthrough** | Clean white slides: big "94%", a chart, route diagrams, tech-stack diagram, business case with Wolt logo, call-to-action diagram | Point-of-view photos and video from Snap Spectacles, plus the mock store upstairs |
| **λpump** | Storytelling: stick-figure persona, big-number slides, a slide of their paper, before/after (control room → dashboard) | Dashboard screenshots, not live. QR during Q&A |

**The 2-minute submission videos** (what peer reviewers see first):
- **Wavelet:** a vertical phone vlog. Hook "If you want to see the coolest graphics you've ever seen, stick around", team-at-work shots, equations, then about 60% screen recording of the simulation.
- **LoreDash:** 100% screen recording with voice-over. Starts from Wikipedia's Random article button, montages many generated games, ends with QR + "Try the fully functional demo".

## 5. Presentation lessons

- **Rehearse for failures; 3 of 5 had one.** LoreDash's sound died (he held the mic to the speaker), DroneStalker had sound issues, Wavelet's GPU was slow. All recovered with a joke. Keep a recorded fallback demo.
- **Test on the big screen.** "Hard to navigate on a massive screen… looks quite a lot worse on the projector" (Wavelet). Use high contrast, large UI and zoom.
- **Prepare the "who did what" answer:** one sentence per person.
- **Prove it's live and built this weekend.** Say "this is live" while it runs. Declare anything pre-built.
- **QR code on the last slide, kept up during Q&A.**
- **Keep one visual style;** the best decks look like the product.
- **Multiple speakers are fine with clean, named handovers** ("I'll hand over to Cody").

## 6. Defence Hackathon 2026 pitches (side event, 5-minute format)

- **17Tech (main prize winner):** two Sun Tzu quotes frame the whole pitch, leading to the question "how do you make a ghost army today?". Then a live hardware demo (a phone triggered by remote command), a scale concept, cost numbers (€50–200 per node, €4–17k per deployment), and an ask with next steps ("would you like to help us?").
- **Are ya winning son? (finalist):** first line "the speed of action is itself a weapon", quantified pain (2–4 weeks of manual work), a concrete scenario (enemy platoon, 6 hours), product intro, live web demo, team close ("three high school students").

Both confirm the pattern: a strong first line, a quantified pain, a live demo, then a clear ask.

## Gaps

- No 2024 or 2023 finalist pitch videos are online, so the analysis is mostly Junction 2025 (see `junction-videos.md` gaps).
- No frames for the Defence videos, and small on-screen text was unreadable in the 320×180 thumbnails.
- Auto-captions misspell names and terms ("Lord Dash" = LoreDash, "sensor fusion" = Sensofusion).
