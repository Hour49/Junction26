# Ranking template and scoring scale for /challenge-pick

## Criteria and weights (default; Madalina can change them, e.g. "weights: fit 30, crowding 5")

Score each criterion 1-5. Weighted total = sum(weight x score) / 100, so the maximum is 5.00.
If weights are changed, they must still add up to 100; show the new weights in the table header.

| # | Criterion | Weight | 1 = | 5 = |
|---|---|---|---|---|
| 1 | Team fit | 20 | needs skills we lack (hardware, ML training, deep domain) | voice/LLM agents, productivity/civic, Android/frontend: our track record |
| 2 | Rubric scorability | 15 | vague or subjective, no rubric | clear weighted rubric, or a metric we can measure in the demo |
| 3 | Wow demo in 38 h | 15 | nothing visible until Sunday | live, visual moment a peer gets in 20 s, buildable by Sat evening |
| 4 | Data / API / hardware access | 10 | nothing given, or only after NDA/late | real data or API usable on Friday night |
| 5 | Crowding (inverse) | 10 | very popular (big prize, famous brand, easy idea) | few teams likely (niche, hard, unglamorous) |
| 6 | Partner value and path to real use | 10 | small prize, no follow-up | big prize, "considered for real development", pilot path |
| 7 | Main-prize potential | 10 | hard to explain to peers; no jury lens | problem-first, shows agent failure + eval, come-back value |
| 8 | Tech-challenge stacking | 10 | no natural tech partner | 2+ tech challenges fit naturally (Gemini, Modal, Featherless, Exa...) |

## ranking.md template

```markdown
# Challenge ranking - Junction 2026

Date: YYYY-MM-DD HH:MM (Helsinki) · Author: /challenge-pick
Based on core.md: <status line from 04-pitch/core.md>
Challenges compared: <n> (deep pass) · triaged out: <names, or "none"> (see shortlist.md)

## Recommendation
**Take: <challenge> - idea "<idea name>".** Score <x.xx>/5.
- Why 1 (with file link, e.g. [fit](<slug>/fit.md))
- Why 2
- Why 3
- Main risk and how we reduce it:
- Runner-up: <challenge> (<x.xx>). Switch to it if: <condition, e.g. "the partner says the data arrives Saturday">.
- Decide by: Fri ~21:00, after talking to the partner reps. Post the decision on the team board.

## Scores
Weights: fit 20 · scorability 15 · wow 15 · data 10 · crowding 10 · partner 10 · main prize 10 · stacking 10 (= 100)

| Challenge | Fit (20) | Score (15) | Wow (15) | Data (10) | Crowd (10) | Partner (10) | Main (10) | Stack (10) | **Total /5** |
|---|---|---|---|---|---|---|---|---|---|
| <name> | 4 | 3 | 5 | 4 | 2 | 3 | 4 | 3 | **3.70** |

Arithmetic for the winner: (20x4 + 15x3 + ...)/100 = 3.70.
One-line reason per low score (1-2): <...>

## Top idea per challenge
| Challenge | Top idea | One-liner | Demo wow | The one number |
|---|---|---|---|---|

## 5 questions for each partner rep (ask on the floor, Fri 19:30-21:00)
### <Partner> - <challenge>
1. <status quo: "How is <job> done today, and what goes wrong most often?">
2. <pain number: "How often / how much does it cost?">
3. <data: "What data or API do we get, when, and in what format?">
4. <judging: "Who judges, and what would make you take a project into real development?">
5. <idea test: "Would <top idea> help? What is missing?">

## UNVERIFIED and open items
- <item> - <how to check it>
```

Rules for the questions: open questions about the partner's real world (Mom Test, see
01-playbooks/market-research.md §2.3), never "do you like our idea?" until question 5. Take them from each
`brief.md` "Questions for the partner rep" and `fit.md` "Deal-breakers", and make them specific to this partner.
