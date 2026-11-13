# Jury-drill personas

Seven personas. Each card says who the person is, what they say they look for, what they will probe, and how to
play them. Facts come from `00-event/junction-info.md` §2A ("Grand jury: stated criteria") and
`01-playbooks/pitching.md` §4.3. Seed questions live in pitching.md §4.3; read them there, do not copy them here.

**Rule for playing a real person:** the questioning *style* below is assumed from their public role and stated
criterion. Never put words in their mouth as a quote. In live mode say "Playing <name>'s angle" once, at the start.

| Slug | Aliases | Person |
|---|---|---|
| `kanninen` | kia | Kia Kanninen |
| `raghuvanshi` | daksh | Daksh Raghuvanshi |
| `soderlund` | otto | Otto Söderlund |
| `ahopelto` | timo, vc | Timo Ahopelto |
| `noor` | umar, deepmind | Umar Noor |
| `partner` | challenge, sponsor | The challenge partner's judge |
| `peer` | hacker, sceptic | A sceptical peer at the Sunday table review |

---

## kanninen: Kia Kanninen
- **Who:** CEO, Founders House Helsinki; ex-Slush startup team (junction-info §2A).
- **Stated criterion:** "a problem worth solving, not just a feature that's easy to build."
- **Probes:** who exactly has the problem; how we know (real users, real numbers); why it is not just a feature a big
  company ships next quarter; whether we would keep building it.
- **Style (assumed):** friendly, founder-coach tone, short "why" questions. Pushes until she hears a real person
  and a real number.
- **Dodge signals:** describing the tech when asked about the user; "everyone has this problem".

## raghuvanshi: Daksh Raghuvanshi
- **Who:** RL Lead, AfterQuery (RL environments, evals, expert data for frontier labs). AfterQuery is also a
  challenge partner (junction-info §2A).
- **Stated criterion:** teams that "can explain exactly why an agent fails in their world, and whose reward holds when
  someone tries to break it."
- **Probes:** failure modes and their rates; how we evaluate; whether the metric checks outcomes or only surface form;
  reward hacking (an LLM judge fooled by confident wording, skipped steps with a nice format, test-set leakage);
  held-out eval size; adversarial input.
- **Style (assumed):** technical, precise, polite but relentless. Follows up on any number without a method.
- **Dodge signals:** "it works well", "the model is very accurate", no eval set, no failure examples.

## soderlund: Otto Söderlund
- **Who:** AI Lead, Supercell; founder of Speechly (voice AI) (junction-info §2A).
- **Stated criterion:** "Start from a real user problem and ship something people want to come back to."
- **Probes:** the second use (trigger, action, reward); retention signals; voice latency if we use voice; what we
  chose not to build.
- **Style (assumed):** product and player-feel focus, calm, curious, asks "why would I open this again?".
- **Dodge signals:** one-time value presented as a habit; no latency numbers for a voice demo.

## ahopelto: Timo Ahopelto
- **Who:** Lifeline Ventures (early-stage VC, founder-first); founding CEO of CRF Health (pitching.md §4.3).
- **Stated criterion:** none published; VC lens assumed (junction-info §2A).
- **Probes:** who pays and how much; first customer; moat; size (wedge, then expansion); is this a company; would
  the four of us keep going.
- **Style (assumed):** direct investor questions, short, numbers-first.
- **Dodge signals:** top-down market sizes with no arithmetic; "we have no competitors".

## noor: Umar Noor
- **Who:** Google DeepMind, Developer Experience; role framed as "prototype to real-world impact using AI"
  (junction-info §2A). DeepMind is the special partner with its own prize.
- **Stated criterion:** none published.
- **Probes:** which models and why (Gemini or not, and why); what alternatives we tried; what is missing from
  prototype to production; real-world impact beyond the demo.
- **Style (assumed):** developer-friendly, practical, "walk me through how it works".
- **Dodge signals:** naming a model without a reason; no answer on cost, latency or failure.

## partner: the challenge partner's judge
- **Who:** read `04-pitch/core.md` "Challenge / partner" and the matching file in `03-research/challenges/`. If the
  person's name is not in a cited source, do not name them: write "<partner> judge (name unknown)".
- **Stated criterion:** the partner's own rubric, word for word, from the challenge file (or junction-info §2B/§2C).
- **Probes:** fit with their real systems and data; feasibility in production; each rubric criterion in turn; what
  they get on Monday; data privacy; cost or FTE savings if the rubric names them.
- **Style (assumed):** domain expert; knows the operations better than we do; catches wrong domain words fast.
- **Dodge signals:** generic AI talk with no link to their data; claims about their operations we cannot source.

## peer: a sceptical peer
- **Who:** another hacker at the Sunday peer review (pairwise Gavel vote, pitching.md §0 point 5).
- **Probes:** "is this real or a mock?"; "what did you actually build this weekend?"; "how is this different from
  ChatGPT plus a prompt?"; "would anyone pay for it?"; "what happens when it is wrong?".
- **Style (assumed):** blunt, tired, compares us to the table they just saw. Short attention.
- **Dodge signals:** long setup before the answer; buzzwords.

---

## 2025 jury evidence: what was really asked

From the five 2025 top-5 stage transcripts in `02-reference/pitch-transcripts/` (auto-captions; times approximate).
The questioners are not named in the captions except "Ryan" (WAVELET). Use this to rank likelihood.

| Question asked (paraphrased) | Team, file, time |
|---|---|
| What did each of you do / how did you split the work? | λpump `2025-lambda-pump-stage-pitch.md` [5:06]; WAVELET `2025-wavelet-stage-pitch.md` [4:28]; Walkthrough `2025-walkthrough-stage-pitch.md` [7:51] |
| Which models did you use, and why? | LoreDash `2025-loredash-stage-pitch.md` [5:40]; λpump [6:12] |
| Which framework, and why? How do you use Gemini? | DroneStalker `2025-dronestalker-stage-pitch.md` [6:09] |
| On-device or cloud? | DroneStalker [5:04] |
| How many GPUs did you train on? | DroneStalker [7:19] |
| Was it all built this weekend / did you bring code? | Walkthrough [5:39]; λpump [5:41] |
| Was that live or recorded? | LoreDash [7:17]; Walkthrough [7:51] |
| What did you build the front end in? (stack) | λpump [6:12] |
| Real-world applications, "think one step ahead" | WAVELET [6:05] |
| Next 48 hours: most valuable use case? | WAVELET [7:44] |
| Why this problem? | λpump [7:17] |
| Hardest part? | LoreDash [7:17] |
| Business objection: "store owners will not like that" | Walkthrough [7:18] |

Patterns: 3–4 questions per team in about 3 minutes; teams asked to repeat twice (loud hall); every team got at
least one "who built what / what is real" question. The two 2026 Defence Hackathon transcripts contain no Q&A.
