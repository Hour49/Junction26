# TODO for Bogdan (review and decide)

Updated 2026-11-10 by Madalina. Only items that need Bogdan's review are here.

- [ ] **Human-voice checklist** `01-playbooks/human-voice.md` (draft, 2026-11-10). A last-step check so spoken
  scripts don't sound machine-written. Built but NOT wired into any skill. Decide: adopt or drop; if adopt, which
  skills (/pitch, /easy-pitch, /pro-pitch, /deck notes, /jury-drill answers, /team-intro), and whether to merge the
  three word lists into it. Open points are in its §5.
- [ ] **Open question: how do we produce the submission video (the technical side)?** `/video-idea` only gives
  concepts, a shot list and a narration outline (ideas, no production). Any suggestions on how to organise the
  real production, and should we improve `/video-idea` or add a production step/skill? For example:
  - Capturing the demo: screen recording tool and settings (OBS? resolution, 16:9), recorded from the live app.
  - Voice-over vs live narration; captions burned in (the stage demo video is silent).
  - Editing: which tool (DaVinci Resolve, CapCut, scripted `ffmpeg` that an agent can run?), who edits, when.
  - Where assets live (`04-pitch/video/`), export format, upload (public YouTube/Vimeo; check the 2026 length limit).
  - Timeline: what must be filmed Saturday so the video is done well before the Sun 10:00 submission.
- [ ] **Open question: a `/research` skill to judge one specific idea, with agents from different aspects?**
  Use case (Madalina): after we pick the track, she has an idea and wants it analysed by several agents, each
  judging it from a different angle, then one verdict. Does Bogdan suggest an existing skill, or should we build
  one that fits what he wants from it (angles, agents, output)?
  What the kit has today (check overlap first):
  - `/market-scan`: 5 agents, deep web research on the idea: competitors, similar ideas, target user, market size,
    problem size. Proposes core.md changes. Research, not a verdict.
  - `/pain-points`: 5 searchers proving people have the problem (quotes + a STRONG/MEDIUM/WEAK verdict).
  - `/jury-drill`: one pass, no agents: judges the idea through 8 jury lenses and lists likely stage questions.
  - `/challenge-pick`: judges challenges (fit, winnability), not one chosen idea.
  Missing: agents that each judge the idea (e.g. buildable in 38 h with our stack, technical risk, partner rubric
  fit, demo "wow", differentiation, user value, jury view) and a combined go / change / drop verdict.
  Kit rule: max 5 agents per skill run (CLAUDE.md).
