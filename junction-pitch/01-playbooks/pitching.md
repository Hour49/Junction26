# Hour49 pitching playbook: Junction 2026 (Espoo, 13–15 Nov)

Researched 2026-11-10 for Madalina (presenter). Inputs: `00-event/junction-info.md` §0, §1 "How judging and pitching work", §2A, §2C, §2E, plus the web sources listed at the end.
Tags: **[FACT]** = sourced. **[2024]/[2025]** = an earlier edition. **[INFERENCE]** = my reasoning. **UNVERIFIED** = check on the platform or Discord on Friday.

---

## 0. Ten things to know (TL;DR)

1. **The 2025 stage pitch was 5 min, not 3, followed by about 3 min of jury Q&A [2025, FACT].**
   - All five 2025 finalist videos run 8:09–9:15 in total (YouTube `lengthSeconds` 488–555).
   - DroneStalker said on stage: "we're only meant to have five minutes". The host cut Walkthrough at about 5:05 ("Time's up").
   - In 2024 the pitch was exactly 3 min, mics were cut at time, and hackers voted for the winner [2024, FACT].
   - **2026 is confirmed: exactly 3 min, mic killed at time, then 3 min of jury Q&A** (Junction 2026 participant info, "Pitching" section, pasted by Madalina 2026-11-10). Prepare the 3-min pitch only, and train for Q&A.
2. **Q&A is part of the jury pitch.** These questions came up across the five 2025 finalists:
   - **"Who did what?"**: asked of 3 of 5 teams.
   - **"Which models and why?"** / **"Which framework, why?"**: 3 of 5.
   - **"Was that live or recorded?"** / **"Was it all built this weekend?"**: 2 of 5.
   - **"Real-world application / the next 48 h?"**: 1 of 5.
   - **A business objection** ("store owners won't like this"): 1 of 5.
   - **"On-device or cloud?"**: 1 of 5.
   - **"Why this problem?"**: 1 of 5.
   - **"Hardest part?"**: 1 of 5.
3. **Audio failed for 2 of the 5 finalists in 2025** (LoreDash held the mic to a speaker; DroneStalker lost time). WAVELET's live demo had about 40 s of dead air while the GPU loaded.
   → **Every embedded video must work silently, with burned-in captions. You narrate live. Have the demo already running before the pitch starts.**
4. **The deck is the pptx uploaded to the platform.** You do not present from your own laptop, and any video must be embedded in the slides [2024, FACT, from Junction's "Pitching" Notion].
   - **Google Slides → pptx export drops or breaks embedded video** (multiple secondary sources). Re-insert the video in PowerPoint and test the pptx on a second machine.
5. **Peer review is pairwise (Gavel)** [2024, FACT]. A reviewer judges your project as "better or worse than the one I saw immediately before", and the vote cannot be undone.
   → What matters is being *more memorable than the table next to you*: a one-line identity, a visible 30-second wow, and a number.
6. **The winners had three things in common:**
   - something technically real and visual, demoed (WAVELET's GPU Maxwell sim, DroneStalker's 50% better than the published baseline);
   - an entertaining delivery (Frank Sandqvist won 2024 with an AI-generated rap video, and 2nd place in 2025 with Game Boy-style games);
   - one sharp idea.
7. **Speak this jury's language** (their own words, from the 2026 site):
   - Kanninen: "a **problem worth solving**, not just a feature".
   - Raghuvanshi: "**why an agent fails**" and a "**reward that holds when someone tries to break it**".
   - Söderlund: a "real user problem", something people "**come back to**".
   - Ahopelto: VC lens. Lifeline backs founders "pre-PowerPoint", so the **team** matters.
8. **One person speaks, and the others handle the demo or the clicker.**
   - Junction advises one speaker on stage [2024].
   - Four of the five 2025 finalists switched speakers, and it cost them time. The jury still asks "who did what", so have that answer ready instead of rotating speakers.
9. **Submit early.** The final deadline is Sun 10:00. Freeze features at 06:00. Upload the video by 08:30, and set the project to FINAL by 09:30.
   - LoreDash (2nd overall) made "all this presentation and most of the editing … this morning", which is survivable but painful.
10. **An agent drafts; the human owns the story, the voice and the truth.** See §5.

---

## 1. Formats and script templates

**Word budget:** speak at about 130–140 words per minute under stress. That gives:
- 30 s ≈ 65–70 words
- 2 min ≈ 260 words
- 3 min ≈ 390 words
- 5 min ≈ 650 words

Leave 10% slack for applause or laughs and for clicks.

**Write one "core message" block first and reuse it everywhere:**
- **Name** (≤30 chars)
- **One-liner:** "X helps [specific user] do [job] in [time/cost] instead of [status quo]."
- **The number:** one measurable result, such as accuracy against a baseline, minutes saved, or € saved.
- **The wow moment:** the 5–10 s of demo that makes people say "oh".
- **Why it's hard:** one sentence on the technical core.
- **Why us:** one sentence.

### (a) 30-second elevator / team intro to partner mentors (Fri 18:00–21:00 and later check-ins)

The goal is to get rubric intel and a partner champion, not to sell. Ask more than you tell.

```
[5 s]  Hi, we're Hour49 — four engineers from Cluj, Romania. We build voice and LLM agents
       and practical civic/productivity tools; we won 1st in AppDev at PoliHack Cluj.
[10 s] We're looking at your <challenge>. Our read: the real pain is <problem in their words>
       for <user>. Is that right?
[10 s] We're thinking of <one-line idea>, measured by <metric>. What would make this
       something you'd actually use after Sunday?
[5 s]  Which criterion matters most to you, and can we come back tomorrow morning to show progress?
```

- Write down their exact words. Quote them on the stage slide ("HSY told us…").
- λpump and Sonaptics both leaned on partner understanding; DroneStalker and WAVELET thanked the partner by name on stage.

### (b) 2-min peer-review table demo (Sun ~10:00–12:00, repeated 20–40 times)

Reviewers judge pairwise and fast. Lead with the product, not the backstory: judges score better when the first sentence says what it does and for whom (dev.to judge notes). **Put the laptop in the visitor's hands within 30 s.**

```
0:00–0:10  HOOK + IDENTITY  "<Name>: <one-liner>." (point at the screen, already on the start state)
0:10–0:30  PROBLEM, ONE NUMBER  "<user> loses <N min/€> every <period> because <cause>."
0:30–1:30  DEMO, VISITOR DRIVES  "Try it: say/type <prepared input>." → wow moment at ~0:50.
           Narrate only what they can't see: "behind this, <agent/model> just did <hard thing>."
1:30–1:45  PROOF  "We measured <metric> vs <baseline>: <result>." (poster/second screen with the chart)
1:45–2:00  CLOSE  "If you remember one thing: <one-liner>. We're table <N>." (+ QR to video/repo)
```

**Table kit:**
- A second screen or tablet looping the 30-s silent demo GIF.
- A printed A4 sheet with the name, one-liner, the number and a QR code (pairwise reviewers need to recall you).
- A reset button or a "fresh session" shortcut.
- Pre-typed inputs on the clipboard (Devpost: skip mundane steps and keep paste-ready text).
- An offline fallback video on the desktop.

**Rotation:**
- Two people at the table in 45-min shifts. Madalina takes the first and busiest shift.
- One technical person is always present for "how does it work?".
- The others go review: each participant must review about 15 projects, or the team may get a penalty [2024].

**Do not** read slides at the table. **Do** ask "what would you use this for?" and note the answers; they become Q&A ammunition.

### (c) Partner / challenge judging pitch (Sunday morning, format set by each partner; UNVERIFIED)

Partners score against their own rubric, so **mirror the rubric verbatim**. Typical criteria are relevance, novelty, technical quality, UX, completeness/demo-ability and feasibility/impact (Junction Terms).

```
0:00–0:15  "For <partner>'s <challenge>, we built <Name>: <one-liner>."
0:15–0:45  Their problem, in THEIR words (quote from the Friday conversation) + their data we used.
0:45–2:15  Demo on THEIR data / API / hardware. Name each rubric criterion as you hit it:
           "That's the <criterion 1> part…"
2:15–2:45  Feasibility: how it plugs into their stack tomorrow (API, OPC UA, export…), cost, what's missing.
2:45–3:00  "What we'd need from you to pilot: <data access / 2 weeks / a contact>."
```

- If the rubric weights usability heavily (Pfizer 50%, Fingrid UX-only in past years), demo the UX first and show tech second.
- If the brief is metric-gated (Fortum's accuracy gate), lead with the number.

### (d) Stage pitch to the jury (3-min core; 5-min extended; Q&A after)

See the slide-by-slide plan in §2. Script skeleton for the 3-min version (≈390 words):

```
[0:00–0:15] HOOK. A person + a moment + a number. "Right now, beneath our feet…" (λpump) /
            "No one likes grocery stores." (Walkthrough). Never start with "Hi, we are team…".
[0:15–0:45] PROBLEM WORTH SOLVING (Kanninen). Who (a named persona, e.g. λpump's "Jamie"),
            what it costs (one sourced number), why now.
[0:45–1:00] SOLUTION in one sentence + what's genuinely new.
[1:00–1:50] DEMO (embedded silent video, 40–50 s, captions burned in; narrate live).
            Show the wow moment by 1:15.
[1:50–2:15] WHY IT'S HARD / WHY IT HOLDS. The technical core in plain words. For an agent:
            "Here's where it fails, and how we check it" (Raghuvanshi): the eval numbers, an
            adversarial case, a guardrail.
[2:15–2:35] PROOF + RETENTION. Metric vs baseline; why users come back (Söderlund): a daily/weekly loop.
[2:35–2:50] TEAM + MARKET in one breath. "4 engineers from Cluj; we've shipped 4 agent products
            at 4 hackathons this year; 1st at PoliHack." + who pays / how big.
[2:50–3:00] CLOSE. Callback to the hook + one-liner. "<Name>. Thank you."
```

**5-min extension**, if 2026 keeps 2025's format. Add:
- +45 s: a second demo beat (an edge case or failure handling)
- +30 s: architecture
- +30 s: a market or go-to-market path with the partner
- +15 s: roadmap ("the next 48 h")

Do not slow down; add content. Write the 3-min version first, because it is the one that must survive a mic cut.

### (e) 2–3-min submission video (YouTube or Vimeo, public or unlisted; ≤3 min [2024], or ≤2 min per the 2024 rules page, so the sources conflict)

**Target 1:50–2:00** so it satisfies either limit. Keep it a demo, not a talking-heads slide show. MLH: "a demo of their hack, not a presentation". Devpost: "avoid slide decks, keep it short and visual".

```
0:00–0:08  Title card: name + one-liner + the number (text on screen, big).
0:08–0:25  Problem: 1 persona shot / stock clip / screenshot + caption with the sourced number.
0:25–1:20  Screen-recorded demo, real input, cut tight (no loading waits; speed-ramp 2–4× with a
           "4× speed" label, never silent cuts that look faked). Wow moment by 0:40.
1:20–1:40  How it works: one architecture diagram, animated in 3 steps; the hard part; eval result.
1:40–1:55  Team (4 faces + roles, 1 line) + what's next.
1:55–2:00  End card: name, repo URL, QR, partner/challenge name.
```

- Voiceover by the human with the best microphone, recorded in a quiet room (Devpost tip). Burn in the captions.
- Pick music without vocals, low volume.
- **Cut 30–45 s from this video for the embedded stage-deck clip.**
- Upload by Sun 08:30 and check that it is publicly viewable while logged out. Devpost tips: mark it "not made for kids"; YouTube gives the link before processing finishes.

### (f) Written submission (platform: name ≤30, punchline ≤200, description ≤5000 Markdown; limits UNVERIFIED for this event, taken from JunctionX Korea 2026)

- **Name (≤30):** pronounceable, and searchable on the review list. Avoid team-name confusion: the jury and peers remember project names.
- **Punchline (≤200):** `<Name> lets <user> <do job> in <time> instead of <status quo>, using <key tech>. <Number>.` Example shape: "λpump turns blind, energy-hungry wastewater pumps into self-optimising systems: MILP + LLM explanations on real HSY inflow data."
- **Description (≤5000, Markdown).** Use these headers (each one is something a judge looks for):
  ```
  ## The problem          (who, cost, source link; partner quote)
  ## What we built        (3 bullets; screenshots/GIF)
  ## Demo                 (video link, live URL, test credentials, 3-step "try it")
  ## How it works         (architecture diagram, models + why, partner API/data used)
  ## Does it hold up?     (eval: metric vs baseline, failure modes, adversarial tests; for agents: reward/guardrails)
  ## Why people come back (retention loop)
  ## What's next          (pilot path with the partner, 48-h roadmap)
  ## Team                 (4 names, roles, 1-line credibility)
  ## Built at Junction    (what's new this weekend; declare any pre-existing code (Terms §8.2), libraries, AI tools used)
  ```
- Fill the other fields too: up to 5 banner images (the first one is the thumbnail, so use the product screenshot with the name), challenge(s), technologies, source link (public, MIT; no secrets or partner data), demo URL, table number, pptx deck. **Set it to FINAL** [2024: drafts were not reviewed].

---

## 2. Deck for the stage (3-min core, 9–10 slides; extended 5-min version in brackets)

Rules (Junction 2024 Pitching page):
- **pptx uploaded on the platform at final submission**, shown from their machine.
- Any video **embedded in the pptx**.
- One handheld mic.
- No rehearsal slot.
- The mic is cut at time.
- Assume 16:9 on a large projector: high contrast, big type. WAVELET: "it looks quite a lot worse on the projector".

| # | Slide | Time 3-min (5-min) | Content | Visual |
|---|---|---|---|---|
| 1 | Hook | 0:00–0:12 | One sentence + a provocative image or number. Speak before clicking. | Full-bleed photo, ≤8 words |
| 2 | Problem + number | 0:12–0:35 (–0:50) | Persona with a name, the cost (one sourced number), why now (regulation, price change, tech). λpump: "Europe moved to 15-minute electricity pricing last month". Walkthrough: "<10% of Europeans buy groceries online" + chart | One big number, source in 10-pt |
| 3 | User | 0:35–0:45 (–1:05) | Who exactly (a narrow user signals research). The partner quote or the peer-review finding ("12 of 30 visitors said…") | Persona card / quote |
| 4 | Solution | 0:45–1:00 (–1:20) | Name + one-liner + 3 icons for "how it changes the day" | Product screenshot |
| 5 | Demo (video) | 1:00–1:50 (–2:40) | 40–50 s embedded MP4, autoplay, **muted**, captions burned in; narrate live. Fallback: an animated GIF of the same | Full-screen video |
| 6 | Why it's hard / how it holds | 1:50–2:15 (–3:20) | 3-box architecture; the one hard thing; **eval: metric vs baseline; failure cases and how they're caught** (Raghuvanshi) | Diagram + 1 chart |
| 7 | Proof + retention | 2:15–2:30 (–3:50) | The number again (bigger); the "come back" loop (Söderlund): daily trigger → value → memory | Chart / loop diagram |
| 8 | Market / path | 2:30–2:40 (–4:20) | Who pays, rough size (top-down, sourced), first customer (the partner) | 3 numbers max |
| 9 | Team | 2:40–2:50 (–4:40) | 4 photos, role + one credential each, the track record line | Photos |
| 10 | Close / ask | 2:50–3:00 (–5:00) | Callback to the hook + one-liner + "next: pilot with <partner>". **Leave it up during Q&A**, with a QR code to the live demo | Name + QR |

- **Backup slides** after the close, for Q&A: architecture detail, an eval table, a failure-case gallery, cost per run, a privacy/data note, and the "built this weekend vs before" list.
- **Market:** at a hackathon, keep it to one slide. VCs know hackathon TAM numbers are fiction; a believable first customer beats "€40B market".

### Presenting the team credibly

- **Lead with shipped evidence**, not titles: "We've built four agent products at four hackathons this year: a voice-first anti-to-do list (1st place AppDev, PoliHack Cluj), an adaptive planner, a prompt coach for BMW, and a city-hall paperwork agent with a tamper-evident ledger." This shows velocity and that agents are our domain.
- **One credential per person, tied to the project:**
  - Bogdan: backend/AI engineer at ERNI; built the agent harness we used.
  - Tudor: backend, systems/security; built <X>.
  - Beatrice: frontend/Android at Garmin; built the UI.
  - Madalina: product and pitch; ran the user interviews.
  - (Fill <X> on Sunday with what each person actually built. The jury asked "who did what" to 3 of 5 teams in 2025.)
- **Origin framing:** "four engineers from Cluj-Napoca, Romania" is distinctive at an event with 100+ nationalities. Use it once, briefly.
- **Do not oversell** (Junction's own pitching guide: "Don't Oversell or Exaggerate … focus on what you've achieved"). Walkthrough opened with a concept video that was "not exactly our product", and the jury immediately asked whether it was built that weekend. Label any concept or vision footage on screen as "Vision" and any real footage as "Live / built this weekend".
- **Ahopelto lens:** Lifeline invests on "vision and capability rather than early traction". The team slide is where you show capability. A line like "we'll keep building this; we've worked together on 4 builds in 11 months" signals a durable team.

---

## 3. What won at Junction: evidence

### 3.1 Junction 2025 top-5 pitch videos (Junction YouTube channel, uploaded 22–23 Dec 2025; transcripts pulled with youtube-transcript-api)

All five were about 5-minute pitches plus about 3 minutes of jury Q&A.

| Team (result) | Video | Pitch structure (actual) | Notable moves | Jury questions |
|---|---|---|---|---|
| **WAVELET** (1st, €10k; Sensofusion Radio City) | [Uh3yPQuee1g](https://www.youtube.com/watch?v=Uh3yPQuee1g) (9:15) | Thanks partner → one-liner "a powerful and accurate radio wave sim" → why this challenge → tech (pure C++, OpenGL/OpenMP, Maxwell's equations) → **live demo** (about 40 s load stall) → "no lightweight tool exists, only commercial/MATLAB" | Hard real tech, spectacular visual, honest ("we thought it looked cool, so we made it") | Who did what and how did you decide? Real-world applications, "think one step ahead"? Next 48 h, most valuable use case? |
| **LoreDash** (2nd, €7.5k; Frank Sandqvist solo, Supercell) | [43uQE6cZGXU](https://www.youtube.com/watch?v=43uQE6cZGXU) (8:15) | Relatable hook (the Wikipedia random-button rabbit hole) → "does any of it stick?" → gamified learning comps (Kahoot, Duolingo, GeoGuessr) → "could we turn random articles into games?" → demo → pipeline (Gemini plan → assets → Gemini Pro code → ElevenLabs SFX) → self-deprecating humour ("67, as the kids say … shows how old I am") → Lyria live music → ran out of time, QR to live URL | Fun, personality, a clear pipeline, QR code to try it. Survived broken audio | Which models and why? (Flash crashed at runtime → Pro.) Hardest part solo? Was that live generation or recorded? |
| **DroneStalker** (top 5; Sensofusion event cameras) | [5x4mQtjzQB0](https://www.youtube.com/watch?v=5x4mQtjzQB0) (8:34) | Opens with its own AI "Commander" voice roasting the user (laughter) → "blow everything out of the water" → designer on the gamified UI → YOLO 5→11→12 → re-uploaded the 200 GB dataset to HF → LSTM **beats all models in the FRED paper by about 50%, 300k params, CPU** → team + live URL | Measurable win against a published baseline, humour, experiential demo. Three speakers cost time | On-device vs cloud? Framework and why? How is Gemini used? How many GPUs? ("zero, CPU") |
| **Walkthrough** (top 5; Wolt) | [9KT34TKEBJ0](https://www.youtube.com/watch?v=9KT34TKEBJ0) (8:46) | "No one likes grocery stores" → 1.5–2 h a week, three time sinks → "why not order online? <10% do" + UK chart → Snap Spectacles AR concept → admitted "we were a bit lying, that was not exactly our product" → real build (mock store upstairs, Go backend on GCP, image classification) → cut off at time | Strong problem framing with data; physical mock store; props on stage | Was it all built this weekend? Business objection (store owners lose basket size → ads?). Was the video what you built? Who did what? |
| **λpump** (top 5; HSY & Valmet) | [8yl6ji8T0lc](https://www.youtube.com/watch?v=8yl6ji8T0lc) (8:08) | Visceral hook ("beneath our feet…") → persona **Jamie**, a plant manager → why now (15-min electricity pricing) → numbers (one station ≈ 500 households; >$100k losses) → "we read the academia" → MILP + reasoning model, wrote a paper → UI demo → "Jamie is a lot happier" → global scale via Valmet → thanks | Best storytelling structure of the five: persona, stakes, resolution. One speaker | Who did what (team of 4, one speaker)? Stack: mobile or desktop? Which models/algorithm? Why pumps? |

**Lessons [INFERENCE from the five]:**
2. Four of five invited the audience to try it (LoreDash QR, DroneStalker live Vercel URL, WAVELET live sim, Walkthrough mock store upstairs).
2. Every finalist had a live or try-it-yourself URL or QR code.
3. Humour and personality were prominent in LoreDash (2nd) and DroneStalker; WAVELET was dry but honest. Personality helps, but it does not replace the artefact.
4. The jury probes authenticity (live or recorded? built this weekend?) and team contribution.
5. Technical hiccups did not disqualify anyone (WAVELET's stall, two audio failures). Recovering calmly is part of the score.

### 3.2 Frank Sandqvist (won 2024; 2nd in 2025; over €20k from Junction) ([Junction blog, 2026-04-01](https://www.hackjunction.com/blog/frank-sandqvist-story))
- 2024 BREAKDANCE: a gamified inventory app, solo. "His presentation was supported by an engaging AI-generated rap video, which in his opinion may have boosted him to win."
- His tips, verbatim:
  - "Identify what you're good at"
  - "Get a team and play into everyone's strengths"
  - "Make something that makes you truly excited"
  - "Have the final product look clean and realistic in the presentation, present it in an interesting and fun way to catch people's attention!"
- He reads the tracks on the train to decide how to apply what he already knows to the challenges. That is the same as our plan: match the challenge to our voice/agent strengths.

### 3.3 Junction's own guidance
- **"Pitching" Notion, Junction 2024** (parsed via the Notion API):
  - "Each team has exactly 3 min for their pitch. After the time is up, the mics will be killed to keep the competition fair."
  - "There will be no time to separately practice the pitch after the review period has ended."
  - "one hand held mic per team … We advise that one person is on stage."
  - "Everything (demos, videos etc.) needs to be included in the slides that you submit in pptx form … You WILL NOT be showing the slides from your computer."
  - A recorded video pitch was allowed instead of speaking.
- **"Reviewing" Notion, Junction 2024:**
  - Gavel pairwise: "for every submission after that, you'll decide whether it's better or worse than the one you looked at immediately beforehand … Once you make a decision, you can't take it back."
  - Review at least 15 projects, or the team may get a penalty.
- **"How to pitch your idea at a Hackathon", Junction Medium, Oct 2023** (read via the Wayback Machine). Five dos and five don'ts:

  | Do | Don't |
  |---|---|
  | Start with a compelling, relevant story | Jargon overload |
  | User-centricity ("shows you have done user research") | Oversell or exaggerate |
  | Demonstrate a prototype | Long-winded pitches |
  | Highlight team expertise | Neglect questions |
  | Practise, practise, practise | Disregard feedback |

### 3.4 Devpost, MLH and judge advice (general hackathon)
- **Devpost, "How to present a successful hackathon demo":**
  - Set the scene in a few sentences (the why).
  - Demo the working project: name key tech and impressive challenges, and skip mundane steps such as logins, with paste-ready text on the clipboard.
  - Close with a sentence or two of vision.
  - Submit early, with screenshots and a video.
- **Devpost, "6 tips for making a hackathon demo video":**
  - Leave 2–3 hours of buffer before the deadline.
  - Write the script yourself ("Try to avoid ChatGPT here if you can"), structured as intro, idea, components, demo, closing.
  - Lead with the elevator pitch in the first seconds.
  - Don't speed up the audio to fit.
  - Use fast, familiar tools (PowerPoint/Google Slides/Canva, OBS, phone screen recorder).
  - The best microphone records.
  - Upload to YouTube early.
  - Check privacy settings.
- **Hackathon judge notes** (dev.to, "What judges actually score", one judge's experience):
  - A working end-to-end path beats ambition shown on slides.
  - First sentence: what it does and for whom.
  - Narrow scope, done well.
  - A one-line identity "you want a judge to repeat to another judge an hour later".
  - Judges asked "who is this for, specifically?", "what did you build during the event?" and "what breaks first at scale?" (naming a weakness raised scores).
  - Polish beyond readability, stack choice and slide decks barely moved scores.
  - Keep a 60-s screen-capture backup.
- **MLH:** expo/science-fair judging, where each project should be seen at least 3 times; equal-weight criteria in MLH-derived rules; "describe what you did for each criterion".

---

## 4. Delivery

### 4.1 Rehearsal plan (times are Helsinki)

| When | What | Who |
|---|---|---|
| Fri 21:00 | After the challenge decision, write the core-message block (§1) and get team sign-off. Start a `04-pitch/` folder | Madalina (agent drafts) |
| Sat 12:00 | Deck v0 (text only, 10 slides) + video shot list. Test the pptx video-embed pipeline with a dummy MP4 **now** | Madalina |
| Sat 16:00 | Record raw demo footage of whatever works (insurance) | Beatrice |
| Sat 20:00 | Deck v1 with real screenshots. **Rehearsal 1** (3-min), recorded on a phone, watched back once | Madalina + 1 |
| Sat 23:00 | Rehearsal 2 in front of 2 outsiders (another team or a mentor). Ask them to repeat the one-liner back. If they can't, rewrite it | Madalina |
| Sun 02:00–05:00 | Sleep at least 3 h (the presenter's voice and recall matter more than one more feature) | Madalina |
| Sun 06:00 | **Feature freeze.** Record the final demo footage. Cut the 30–45-s stage clip and the 2-min video | Beatrice + Madalina |
| Sun 07:30 | Rehearsals 3–5: 3-min with a hard timer; the 5-min extension once; 2-min table demo three times. Teammates fire Q&A cards (§4.3) | All |
| Sun 08:30 | Video uploaded and checked logged-out. pptx exported, embedded video tested on a second laptop | Madalina |
| Sun 09:30 | Submission FINAL (no editing at 09:59) | Madalina |
| Sun 10:00–12:00 | Peer-review table demos (live rehearsal × 20) | Shifts |
| If top 5 | No rehearsal slot [2024]. Run the 3-min version once in a corridor with a timer, then go | Madalina |

**Delivery rules:**
- Memorise the first 30 s and the last 10 s word for word. Bullet-point memory for the middle.
- One speaker. A teammate stands ready for technical Q&A, and Madalina hands off by name.
- Hold the mic close to the chin and keep the distance constant (handheld mic).
- Face the audience. Know which slide comes next before clicking.
- Pause after the number.
- If cut at time, the last thing said should already be the one-liner. Put the "close" content at 2:45, not 2:59.

### 4.2 Demo-failure backups (layered)
1. **Stage:** the demo is an embedded MP4 in the pptx, muted and captioned, so nothing is live by default.
   - If 2026 allows a live demo, still keep the video on the slide as a fallback, and keep the app pre-loaded and warmed up (WAVELET lost about 40 s to a cold GPU).
2. **Embedded video won't play:**
   - Each video slide gets an **animated GIF** duplicate on a hidden backup slide (GIFs play as images with no codec issues).
   - Plus 3 key screenshots on the next slide with captions.
   - Narrate as if it played.
3. **Audio fails** (2 of 5 in 2025): captions burned in, and the narration is live anyway. Never rely on video audio.
4. **Table demo:**
   - Local build plus seeded demo data. Run it offline where possible (no venue Wi-Fi dependency), and keep a phone hotspot.
   - API keys loaded; rate limits and credits checked; a cached-responses mode ("demo mode" flag) for LLM calls.
   - A pre-recorded 60-s screen capture on the desktop.
5. **Platform outage** (it crashed in 2023): keep the video on YouTube, the deck in Google Drive and on a USB stick, plus a repo README with all links. Screenshot the submitted form.
6. **Spoken recovery line:** "The live version is at table <N> — come break it." Turns failure into an invitation and fits Raghuvanshi's "try to break it".

### 4.3 Q&A preparation

**Q&A rules:**
- Answer in 15–20 s: answer, evidence, stop.
- Repeat or reformulate the question if the hall is loud (twice in 2025, teams said "can you repeat").
- Never bluff. "We haven't measured that; our guess is X because Y" scores well (per the dev.to judge).
- Questions are for the whole team (Madalina, 2026-11-10): whoever knows the answer best takes it. No fixed split by topic.

**Likely questions, by judge**

**Questions asked in 2025 by any jury (prepare all):**
- "Who did what?" Prepare a 4-line answer, 5 s each, said by the speaker.
- "What exactly was built this weekend? Any pre-existing code?" Must match the submission's declaration (Terms §8.2).
- "Was that live or recorded?"
- "Which models and why? What alternatives did you try?" Have one comparison (e.g. Flash vs Pro: speed vs crash rate, like LoreDash).
- "Next 48 h / most valuable use case?"
- "Why this problem?"
- "Hardest part?"

**Kia Kanninen** (problem-first; Founders House, ex-Slush):
- "Who exactly has this problem, and how do you know?" → partner quote + peer-review interviews + the sourced number.
- "Isn't this just a feature <big company> will ship?" → why the workflow or data is specific; what we know that they don't.
- "Would you keep building this?"

**Daksh Raghuvanshi** (RL lead, AfterQuery: RL environments, evals, expert data for frontier labs):
- "Where does your agent fail?" Have a failure taxonomy slide: e.g. hallucinated tool args, wrong tool choice, long-horizon drift, ambiguous voice input, prompt injection from retrieved content. Give rates from your eval.
- "How do you evaluate it? What's your reward or metric, and can it be gamed?" Explain how the metric checks *outcomes* rather than surface form (e.g. an exact state check of the final DB/document, not "LLM says it looks right"). Name the known hacks you tested against: an LLM judge fooled by confident wording, an agent skipping steps but formatting the output correctly, test-set leakage.
- "If I tried to break it, how?" Prepare a demo of an adversarial input being caught: a guardrail, a validation step, a human-in-the-loop.
- "Is your eval set held out? How many cases?" Even 30–50 hand-labelled cases with a pass rate beat nothing. **Build this eval harness on Saturday; it is our differentiator for this judge.**

**Otto Söderlund** (AI lead, Supercell; Speechly voice-AI founder, so our voice work is relevant; a PGC Helsinki 2025 panel he spoke on was headlined "AI does not have taste" (PocketGamer; attribution to him UNVERIFIED)):
- "Why would someone use this a second time? What's the loop?" Trigger, action, reward, investment; show the D1/D7 hook.
- "What's the latency of the voice interaction?" Know the p50/p95 numbers.
- "What did you decide *not* to build?" (taste)

**Timo Ahopelto** (Lifeline Ventures, founder-first, early stage; health-tech operator background, founding CEO of CRF Health):
- "Who pays, and how much?" One pricing hypothesis plus the first customer.
- "Is this a company? Would you four keep working on it?" Give an honest answer; the track record shows the team builds together.
- "What's the moat?" Data, workflow integration, the partner relationship.
- "How big can it get?" A believable wedge, then the expansion.

**Umar Noor** (Google DeepMind, developer experience):
- "How did you use Gemini, and why that model?" (2 of 5 finalists in 2025 used Gemini.)
- "Prototype to production: what's missing?"

**The two unannounced judges:** check the site on Fri/Sat and add their questions.

**Q&A drill:**
- Print the questions on cards. Teammates fire them at random during the Sunday 07:30 rehearsal.
- Target ≤20 s per answer. Record the weak ones and fix the deck's backup slides.

---

## 5. Tooling: fastest path, and agent vs human

### 5.1 Deck
- **Recommended:** draft in **Google Slides** (all four can edit, Junction-like dark theme). Then **File → Download → .pptx**, open it in **PowerPoint** (desktop on the Windows host, or PowerPoint for the web), and **re-insert the MP4 via Insert → Video → This Device**.
  - Google Slides → pptx does not reliably keep video (YouTube/Drive embeds become thumbnails or need internet; secondary sources). Embedding from a file is what makes it self-contained.
  - Test the final pptx on a different machine with Wi-Fi off.
- **Video specs for embedding:** MP4 H.264, 1080p, 30 fps, no audio needed, ≤50 MB per clip, autoplay ("Start: Automatically").
  - Add an animated GIF backup (ffmpeg: `ffmpeg -i clip.mp4 -vf "fps=12,scale=1280:-1:flags=lanczos" -loop 0 clip.gif`), keeping it under about 15 MB.
- **Alternative:** have an agent generate the pptx directly with `python-pptx` from a Markdown outline (it supports embedding movies via `add_movie`), then polish it in PowerPoint. Good for fast iteration of text; weaker on design.
- **Canva:** fastest to look polished, and exports pptx. Video embeds and fonts may not survive export, so the same re-insert test applies. Canva also renders slide-timed videos (Devpost tip).
- **Design rules:**
  - ≤12 words per slide except the backup slides.
  - One idea per slide.
  - Font ≥28 pt, with numbers huge.
  - High contrast; projectors wash out colour (WAVELET).
  - Put a slide number in a corner for Q&A ("back to slide 6").
  - Reuse the team visual identity from the Hour49 site (Eurostile/Michroma, Space Mono, neon-city palette) for recognisability, but keep it legible.

### 5.2 Video
- **Screen recording:**
  - **OBS Studio** on the Windows host: record the browser or the app window at 1080p60 and the mic on a separate track. WSL apps are viewed in a Windows browser, so OBS captures them fine.
  - Quick alternatives: Windows Snipping Tool screen recording, or Xbox Game Bar (Win+Alt+R; one app window only).
  - Android demo: the phone's built-in screen recorder (Beatrice).
- **Editing:**
  - **CapCut desktop:** fastest for cuts, speed ramps, text and auto-captions. **Auto-captions may be Pro-only in 2025–26** (Descript and Filmora claim a paywall; others say free with limits), so check on Friday.
  - Free fallbacks:
    - **Kdenlive** (has Whisper speech-to-text subtitles)
    - **DaVinci Resolve** free
    - `whisper` / `whisper.cpp` → `.srt` → `ffmpeg -i in.mp4 -vf subtitles=in.srt out.mp4` to burn in. Run whisper capped per the machine rules: `nice -n 15 systemd-run --user --scope -p MemoryMax=4G …`, using the small or base model.
  - YouTube's automatic captions are free but not burned in.
- **Voice:**
  - Record the human voiceover first; it sounds more authentic and the jury rewards personality (LoreDash, DroneStalker). Use a phone close to the mouth in a quiet room, or a headset.
  - **AI voice** (e.g. ElevenLabs, a 2025 tech-challenge partner, likely present again) only as a fallback or for a stylised character voice. DroneStalker's AI "Commander" got a laugh; Frank's AI rap video was memorable. A fully AI-narrated pitch risks sounding generic, and Devpost contributors advise writing the script yourself.
- **AI-generated hook assets** (optional, Frank-style): a 5–10-s AI-generated intro visual or jingle can make the pitch memorable. Use it only if it costs under 30 min and the product is done.
- **Music:** royalty-free (YouTube Audio Library), with no vocals under the speech.
- **Upload:** YouTube unlisted or public, "not made for kids", checked in an incognito window. Put the link in the submission and the README.

### 5.3 What an AI agent can draft vs what the human must do

| Agent can draft (fast, verify after) | Human must do |
|---|---|
| Core-message variants (10 one-liners, 5 names checked against the ≤30 limit) | **Choose** the one-liner and the persona; it must sound like Madalina |
| Script drafts per format with word counts against time budgets (130–140 wpm) | Say it out loud, cut what trips the tongue, own the delivery |
| Submission text within the character limits; README; the "built this weekend vs pre-existing" list from `git log` | **Verify every claim and number is true**; declare pre-existing code honestly |
| Slide outline + `python-pptx` generation; architecture diagram (Mermaid → PNG) | Visual judgement on the projector; the final PowerPoint embed test on a second machine |
| Eval harness scaffold, failure-case table, metric-vs-baseline chart from logs | Decide which failure modes matter; run the adversarial demo |
| Q&A bank tailored to the judges; mock-judge questioning sessions | Answer live under pressure; rehearse with a timer |
| Market-size and source research; competitor scan | The partner conversations, real user quotes from peer review |
| Captions via Whisper, ffmpeg cuts, GIF conversion, compression commands | Record the demo and voice; edit for pacing and wow timing; upload and set privacy |
| Checklists and deadline reminders on the team board | Press FINAL on the platform; be at the table; go on stage |

- **Agent limitation to plan around:** agents tend to write generic "revolutionising X" copy. Use them for structure, limits and options; rewrite in plain, concrete words.
- **Agent workflow:**
  - Put `04-pitch/core.md` (the core-message block) in the repo. Every artifact is generated from it, so a change to the one-liner propagates.
  - Agent tasks are posted to the board as bounded briefs: "draft the 2-min table script from core.md, ≤260 words".

---

## 6. Open items to verify on Friday
- 2026 stage pitch length (3 min as in 2024, or 5 + Q&A as in 2025?). Whether a live demo from our own laptop is allowed, and whether the deck must still be pptx on the platform.
- 2026 submission fields and limits, video length (2 or 3 min), and whether a deck upload is required.
- Peer-review mechanics in 2026: the minimum review count and the penalty.
- The two unannounced jury members.
- Whether the partner judging round has its own pitch slot or format per challenge.

---

## Sources
- Junction 2025 finalist pitch videos (Junction YouTube channel; metadata and auto-transcripts fetched 2026-11-10):
  - [WAVELET](https://www.youtube.com/watch?v=Uh3yPQuee1g)
  - [LoreDash](https://www.youtube.com/watch?v=43uQE6cZGXU)
  - [DroneStalker](https://www.youtube.com/watch?v=5x4mQtjzQB0)
  - [Walkthrough](https://www.youtube.com/watch?v=9KT34TKEBJ0)
  - [λpump](https://www.youtube.com/watch?v=8yl6ji8T0lc)
- [Frank Sandqvist story, Junction blog (2026-04-01)](https://www.hackjunction.com/blog/frank-sandqvist-story). Read via the site's `/api/blog/frank-sandqvist-story`.
- [Junction 2024 "Pitching" (Notion)](https://junctionhq.notion.site/Pitching-21bfe4c81be94571a9cda396a3897a9f) and [Junction 2024 "Reviewing" (Notion)](https://junctionhq.notion.site/Reviewing-fff59a118137812eb17fdf07e797aed7). Read via the Notion public API.
- [Junction, "How to pitch your idea at a Hackathon" (Medium, Oct 2023)](https://hackjunction.medium.com/how-to-pitch-your-idea-at-a-hackathon-a95cd3f62f60). Read via the [Wayback snapshot of 2025-04-02](http://web.archive.org/web/20250402065732/https://hackjunction.medium.com/how-to-pitch-your-idea-at-a-hackathon-a95cd3f62f60).
- [Junction 2026 site](https://2026.hackjunction.com/) and [llms.txt](https://2026.hackjunction.com/llms.txt) for the jury quotes and judging flow, via `00-event/junction-info.md`.
- [Devpost: How to present a successful hackathon demo](https://info.devpost.com/blog/how-to-present-a-successful-hackathon-demo)
- [Devpost: 6 tips for making a hackathon demo video](https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video)
- [dev.to: What judges actually score](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)
- [MLH guide: Judging & submissions](https://guide.mlh.com/general-information/judging-and-submissions), [MLH: Using Devpost](https://guide.mlh.io/general-information/judging-and-submissions/hackathon-submission-portal/using-devpost)
- [Anish Athalye: Gavel, an expo judging system](https://anishathalye.com/gavel-an-expo-judging-system/)
- Judge background:
  - [Founders House Helsinki (tech.eu)](https://tech.eu/2026/02/26/founders-house-launches-in-helsinki-to-build-finland-s-next-global-tech-giants/)
  - [Timo Ahopelto (vcsheet)](https://www.vcsheet.com/who/timo-ahopelto)
  - [Lifeline €150M fund (EU-Startups)](https://www.eu-startups.com/2023/05/finnish-early-stage-investor-lifeline-ventures-closes-a-e150-million-fund-to-back-next-generation-success-stories/)
  - [AfterQuery (RL environments job post)](https://www.builtinsf.com/job/software-engineer-rl-environments/9971885)
  - [rl-list.com](https://rl-list.com/)
  - [PGC Helsinki 2025 panel, "AI does not have taste" (PocketGamer.biz)](https://www.pocketgamer.biz/industry/aiba)
  - [Playing with Inference ep. 17, Supercell AI](https://playingwithinference.podbean.com/e/ep-17-how-supercell-is-supporting-ai-native-innovation)
- Tooling (secondary sources):
  - [Google Slides → pptx video loss (SlideModel)](https://slidemodel.com/fix-compatibility-powerpoint-google-slides/)
  - [CapCut captions paywall claim (Descript)](https://descript.com/blog/article/capcut-captions-arent-free-anymore-heres-a-better-option)
  - [CapCut free vs paid (Fluxnote)](https://fluxnote.io/guides/capcut-ai-features-free-vs-paid-2026)
