# Junction 2026: team Hour49 info pack

Compiled 2026-11-10, three days before the event, by an orchestrator plus three research agents covering the event, the challenges and the team.
This file is meant to be read by agents.
- Tags: **[2026]** = confirmed for this year; **[2025]/[2024]** = earlier editions; **UNVERIFIED** = single or secondary source, or inference.
- Sources are inline. Re-check anything marked UNVERIFIED on the platform or Discord on Friday.

## 0. Quick facts (read this first)

| What | Fact |
|---|---|
| Event | Junction 2026, "European Tech Renaissance". 48 h, in person, about 2,000 builders, **€100k** prizes (split not yet published) |
| When | **Fri 13 Nov 16:00 to Sun 15 Nov 18:00**, Europe/Helsinki (**UTC+2**) |
| Where | **Hype Areena, Vanha Jorvaksentie 3, 02320 Espoo** (Kivenlahti metro, end of the M1/M2 line). **Not Dipoli** |
| Key deadlines | Hacking starts Fri 19:30 · **preliminary submission Fri 23:59** · submissions open Sat 12:00 · **final submission Sun 10:00** (late entries at Junction's discretion) |
| Judging | Partners choose their track winners → **face-to-face peer review** Sun morning picks the **top 5** → live stage pitch to a **jury of 7** (**exactly 3 min**, mic cut, then 3 min Q&A) (ceremony 14:00, challenge winners 15:10, overall winner 15:50) |
| Team | **1–4 people**, one project per team. Hour49 = 4 (full) |
| Pre-existing code | Allowed only if **declared** in the submission form (Terms §8.2). Projects must be built mainly during the event |
| Licence | Assume the **public repo is MIT-licensed** (FAQ). No secrets or partner data in the repo |
| Tracks | Hardware (Arduino), Healthcare, AI Infrastructure (Verda), FinTech, Agentic AI, Data, plus cross-track **tech challenges** (credits and "best use of X" prizes) |
| Challenge briefs | **Not public yet.** They appear in the platform "Challenges" tab (login) and the opening videos, Fri 18:00 |
| Platform | [hackjunction.app/hackathons/junction-2026](https://hackjunction.app/hackathons/junction-2026), used for team, submission and review |
| Discord | "Junction Community", [discord.gg/nDgvafhRU4](https://discord.gg/nDgvafhRU4), #announcements |
| Sleep / food | **No sleeping areas** (the venue is open 24 h). Dinner Fri; lunch and dinner Sat. Book a hotel |
| Jury hints | Kanninen: "a problem worth solving, not a feature". Raghuvanshi (AfterQuery): "why an agent fails" and a reward "that holds when someone tries to break it". Söderlund (Supercell): "something people want to come back to" |

## 0.1 Status of the "Junction Challenge Archive" artifact
The artifact at https://claude.ai/artifact/JDrDHBYmsPEtV4T3EEKiXT ("Junction Challenge Archive") belongs to someone else and **could not be read** from this session: both the artifact read and the docs read were refused.
- It is probably built from the public archive at [hackjunction.com/challenges](https://www.hackjunction.com/challenges): 147 challenges from 2017–2025, with rubrics and prizes. That archive is summarised in section 2C/2D below, with the archive's off-by-one year labels corrected.
- To include the artifact itself, share it with this account or paste its content, then add it as section 4.

## 0.2 Hour49 to-do list for Thursday and Friday (derived from all sections)
1. Every member passes the prep checks (`herdr status`, `herdr integration status`, `board read`, smoke worker) and does the 30-min rehearsal. See section 3.
2. Pack: ID, laptop, charger, ethernet cable, headphones, EU adapter, clothes, towel and toiletries, water bottle. Bring your own screen, mouse and keyboard if you want them.
3. Fri 18:00 opening: shortlist 2–3 challenges by fit with our strengths (voice/LLM agents, productivity/civic tools, Android or frontend polish), and check that the rubric is scorable and that real data or hardware is available. Talk to partner reps within the first hour. Decide by about 21:00 and post it as a `board` `decision`.
4. Register the project before **Fri 23:59** (preliminary submission).
5. Stack 1–2 tech challenges (DeepMind/Gemini, Modal, Featherless, Exa, Context, …) that fit naturally.
6. Madalina owns the pitch: deck and video from Sat afternoon, one measurable number on a slide, rehearse a 2-min peer-review demo and the stage pitch. Feature freeze about Sun 06:00; submit well before 10:00.

---

# 1. Event facts and logistics


Researched 2026-11-10. Primary sources: the official site [2026.hackjunction.com](https://2026.hackjunction.com/) (incl. [llms.txt](https://2026.hackjunction.com/llms.txt), last updated 16 Sep 2026), the application/submission platform [hackjunction.app/hackathons/junction-2026](https://hackjunction.app/hackathons/junction-2026) and its public API ([event.getAllFutureEvents](https://hackjunction.app/api/trpc/event.getAllFutureEvents), record updated 2026-10-26), and the [Junction Terms](https://www.hackjunction.com/terms-of-service) (SPA; text read from the site bundle).
Tags: **[2026]** confirmed for this year · **[2025]/[2024]** earlier editions, for reference only · **UNVERIFIED** not confirmed by an official source.

### Key facts
- **Name/theme [2026]:** "Junction 2026: European Tech Renaissance". 48-hour, in-person hackathon. Organisers expect 2,000 builders from 100+ countries, with **€100,000** in prizes. Most challenges are AI, plus software, hardware and physical AI. ([site](https://2026.hackjunction.com/), [llms.txt](https://2026.hackjunction.com/llms.txt))
- **Dates [2026]:** Fri **13 Nov 16:00** to Sun **15 Nov 18:00**. Junction Week pre-events start Mon 9 Nov; their details were "to be announced". ([site FAQ](https://2026.hackjunction.com/))
- **Timezone:** Europe/Helsinki, which is **EET = UTC+2** that weekend (DST ended in October). The platform displays "Europe/Helsinki (+02:00)". The schema.org startDate is `2026-11-13T16:00:00+02:00`. ([platform](https://hackjunction.app/hackathons/junction-2026))
- **NOT Dipoli / Otaniemi.** The venue is **Hype Areena** (also written "Hybridiarena Hype" or "Hype Arena"), **Vanha Jorvaksentie 3, 02320 Espoo** (Kivenlahti). Sources: the [Espoo city listing](https://www.espoo.fi/en/events/espooevents:agp767vqb4), the platform page and [Junction 2025's page](https://hackjunction.app/hackathons/junction-2025). Junction 2024 was at Dipoli, Otaniemi ([Aalto news](https://www.aalto.fi/en/news/europes-largest-hackathon-junction-takes-over-aalto-university)). Junction 2025 was already at Hype ([2025 blog](https://www.hackjunction.com/blog/48-hours-junction-2025)). The site says explicitly: "That is Espoo, not Helsinki." Junction Oy's registered office is Startup Sauna, Otaniemi; this is not the venue.
- **Registration [2026]:** registration has **closed**. Applications closed at midnight 25.10.2026 (GMT+3); the platform shows "Status: Closed, Deadline 25 Oct 2026, 23:59". Entry was free, by application, and every application was reviewed. The only paid ticket is the Investor Pass.
  - Older sources give an earlier deadline of **6 Sep**. These are the Espoo listing and the legacy API at [hackjunction.com/api/events](https://www.hackjunction.com/api/events), which shows `registration_end_time 2026-09-06`. 6 Sep is also the travel-grant deadline. The deadline was later extended to 25 Oct.
- **Contact:** hello@hackjunction.com. The platform contact person is Sophia Vilponen, Head of Communications. In 2024 the participant address was participants@hackjunction.com [2024].

### Getting there
- **Official guidance [2026]:** Kivenlahti is the western terminus of the Helsinki metro. Travel times: about 30 min by metro from Helsinki Central Railway Station, about 20 min by car from central Helsinki, and about 30 min by car from Helsinki-Vantaa Airport. ([site FAQ](https://2026.hackjunction.com/))
- **From Kivenlahti metro:** the arena is "right next to" Kivenlahti metro station ([L-Ark](https://l-ark.fi/?p=15078), [Espoo](https://www.espoo.fi/en/news/2023/05/construction-kivenlahti-hybrid-arena-begins-sports-centre-part-wider-development-area)). The exact walking time was not found.
- **From the airport by public transport (UNVERIFIED, general knowledge):**
  1. Take an HSL I or P commuter train from the airport to Helsinki Central (about 30 min).
  2. Take the M1/M2 metro west to Kivenlahti (about 30 min).

  The trip crosses HSL zones A–C, so buy an ABC ticket in the HSL app. Allow about 75–90 min door to door.
- **Accommodation:** discounted rooms at partner hotels near the venue [2026]. The hotels are not named on the public pages. In 2025 the official accommodation provider was Hotel Matts [2025].
- **Travel grants [2026]:** €300 or €100 grants for international participants. The grant deadline was 6 Sep, and applications are now closed.
- **Invitation letters [2026]:** sent in batches on 11 Oct, 25 Oct and 1 Nov 2026.

### Schedule [2026, "preliminary, times may still shift"]
Source: [site schedule section](https://2026.hackjunction.com/#schedule), cross-checked against the [platform schedule](https://hackjunction.app/hackathons/junction-2026) and API timestamps. All times EET.

**Fri 13 Nov**
- 16:00 Doors open; registration and check-in on the 2nd floor.
- 18:00 Opening Ceremony: practicalities, Google DeepMind keynote, challenge videos.
- 19:30 Hacking starts. The API `startTime` is 17:30Z = 19:30 EET.
- 19:30 Dinner on the 2nd and 3rd floors.
- 20:15 Google DeepMind workshop.
- 20:45 Verda workshop (Loft) and Arduino workshop (Hardware Floor, 5th).
- 21:15 MLH x GitHub session.
- 23:59 **Preliminary submission**. The platform says 23:55. In 2024 this was a draft submission "for a team count".

**Sat 14 Nov**
- 11:15 Cala workshop.
- **12:00 Submissions open** on the Junction Platform (API `submissionsStartTime` 10:00Z).
- 12:15 Ignite Next workshop (5th floor).
- 13:00 Lunch, and Hostinger keynote on the Main Stage.
- 13:45 Modal workshop.
- 14:50 Kiuas workshop.
- 16:45 Exa workshop.
- 17:45 Context workshop.
- 18:00 Dinner.

**Sun 15 Nov**
- **10:00 Final submissions.** API `submissionsEndTime` is 08:00Z = 10:00 EET. Hacking time is about 38.5 h from the 19:30 Friday start.
- 10:30 Review time.
  - llms.txt gives review as 10:00–13:00.
  - The platform lists "Review time 14:00".
  - Read as: peer review in the morning, ceremony at 14:00.
- **14:00 Final Ceremony:** Arduino and Verda keynotes, then the **top 5 pitches**. **Challenge winners are announced at 15:10** and the **Junction winner at 15:50**.
- 17:00 Event ends.
- 18:00 Doors close.

For comparison, [2025](https://hackjunction.app/hackathons/junction-2025) followed the same shape: pre-submission Fri 23:59, final submission Sun 10:00, peer reviewing from 10:00, closing ceremony 14:00, top 5 pitching 14:40, awards 15:45.

### Team rules and eligibility
- **Team size [2026]: 1–4.** Sources: the platform ("Team size: 1-4"), the API (`maxTeamSize: 4`) and the FAQ ("up to 4 people"). In 2024 and 2025 the limit was 1–5.
- **Joining:** you can apply solo or as a team. Team-building happens on site before hacking starts. In 2024 there were also platform match-making and a #teambuilding Discord channel.
- **Eligibility:** "Anyone who builds"; participants are "mainly 18 and over". The 2025 rules said 18 or older. The Terms say you may be in only one team per challenge. The API shows `allowMultipleSubmissions: false`, so each team has one project.
- **Pre-existing code ([Terms §8.2](https://www.hackjunction.com/terms-of-service), current):**
  - "Projects must be built primarily during the Event."
  - "Use of pre-existing code, datasets, or frameworks is permitted only if clearly identified in your Submission in the fields provided on the submission platform."
  - Cheating, plagiarism or misrepresentation leads to disqualification.
  - The 2024 rules were stricter: "No code written before the event", and projects tied to an existing company were disqualified ([2024 rules](https://junctionhq.notion.site/Junction-Rules-5d58563953bd48e4a8740e533ffc5577)).
- **Partner resources (§8.4):** use partner APIs, data and hardware only within the stated limits. Do not probe, reverse-engineer or misuse partner systems.
- **IP: the sources conflict.**
  - The 2026 FAQ says teams keep ownership, but "Submissions are open-sourced under the MIT licence … with your team credited."
  - The Terms (§7.1–7.3) say work stays yours "(or your employer's)". Junction and partners get only a non-exclusive licence to marketing information and recordings. Challenge-specific IP terms may override this by separate agreement.
  - **Assume the repo is public and MIT-licensed; add a LICENSE file.**
- **Judging access (Terms §8.7):** partners may run your submission, call demo endpoints and use the demo credentials you supply.
  - Partners may use it only for judging, and for up to 7 days after the event.
  - Any credentials you supply must be demo/test only, with no personal or live data.
- **Late submissions:** "may be rejected or considered at Junction's discretion" (Terms §8.6). In 2024 the form closed automatically and late entries were not accepted.

### Submission requirements
- **Platform:** the Junction Platform at [hackjunction.app](https://hackjunction.app/hackathons/junction-2026). This is the new platform; the old app.hackjunction.com no longer resolves. One team member creates the project; the [participant tutorials](https://www.junctionplatform.com/tutorials/participants) cover creating a team and submitting a project.
- **2026-specific required fields: UNVERIFIED.** They are not public before the event; check the platform and the Discord #announcements channel on Friday.
- **Required by the Terms (§8.6):** the project must be demonstrable in the specified format (live demo or video). Include the materials needed for evaluation: README, dependencies and limited demo credentials. Disclose any pre-existing code in the platform fields.
- **[2024] required fields** ([2024 Project Submission page](https://junctionhq.notion.site/Participant-Guidebook-Junction-2024-10559a11813780389e0fc382f7ec6ea8)):
  - up to 5 banner images
  - name, punchline and description
  - challenge
  - technologies used
  - a **video pitch, publicly viewable on YouTube or Vimeo**: "not a second longer than 3 minutes". The 2024 rules page said "maximum 2 minutes" instead, so the 2024 sources contradict each other.
  - a pptx or Google Slides deck if you want to pitch on stage
  - demo and source-code links, and whether the source is public
  - table number

  The project had to be set from **DRAFT to FINAL** before the deadline; drafts were not reviewed. A source link was mandatory, and organisers had to be able to access it even if it was private.
- **Platform field limits:**
  - Current platform, as used at JunctionX Korea 2026 (UNVERIFIED for this event): Project name ≤30 characters, Punchline ≤200, Description ≤5000 in Markdown ([team notes](https://github.com/needsbuilder/docdo/blob/main/docs/submission/form.md)).
  - Legacy platform ([JunctionApp schema](https://github.com/hackjunction/JunctionApp/blob/STAG/shared/constants/project-schema.js)): name ≤100, punchline ≤300, description ≤3000, plus source URL, demo URL, video URL, ≤5 images, ≤5 challenges, technologies and table location.

### How judging and pitching work
1. **Partner/challenge round [2026]:** each Challenge Partner picks its own track winners against its own criteria. Winners are announced at the ceremony (15:10).
   - The Terms list typical criteria: relevance to the brief, novelty/creativity, technical quality, UX, completeness/demo-ability, and feasibility/impact.
   - Read the criteria for your specific challenge on the platform.
2. **Main event, top 5 [2026]:** selected by **face-to-face peer review** on Sunday morning after the 10:00 deadline.
   - The API shows `physicalPeerReview: true` and `hasGavelVoting: false`. Teams sit at tables and other participants visit them.
   - Expect to demo your project in person to peers during review time. Keep someone at the table.
   - Back-end for this: Junction's [Gavel fork, platform-integration branch](https://github.com/hackjunction/gavel/tree/platform-integration), last updated Aug 2026.
3. **Grand final [2026]:** the **top 5 pitch live on stage** to the audience and a **grand jury of 7**, who choose the overall winner (15:50). Five judges are named:
   - Kia Kanninen (Founders House Helsinki)
   - Daksh Raghuvanshi (AfterQuery)
   - Otto Söderlund (Supercell AI)
   - Timo Ahopelto (Lifeline Ventures)
   - Umar Noor (Google DeepMind)

   Two more are to be announced.
- **Stage pitch 2026: exactly 3 min, then 3 min of jury questions** (Junction 2026 participant info, "Pitching" section, pasted by Madalina 2026-11-10):
  - The top 5 (picked by peer review) pitch on the streaming stage; Junction fetches them after the review period.
    Top teams are contacted before the Closing Ceremony. No separate practice time after the review period.
  - Mics are killed when the 3 minutes are up. One handheld mic per team; one person on stage is advised.
  - Teams may demo from their **own computer**; Junction checks the connection beforehand.
- **2024, for comparison:** each team had exactly **3 min** and mics were cut at time.
  - Slides had to be the pptx uploaded on the platform, and teams did not present from their own laptop. Any demo video had to be embedded in the slides.
  - One handheld mic was provided, and there was no rehearsal slot.
  - Teams could choose a recorded video pitch instead of speaking on stage. ([2024 Pitching](https://junctionhq.notion.site/Pitching-21bfe4c81be94571a9cda396a3897a9f))
- **[2024] peer review mechanics:**
  - It used a modified Gavel pairwise comparison. Each participant reviewed at least 15 projects, and teams that skipped reviewing could get a score penalty.
  - The top 10 pitched and hackers voted for the winner. 2026 instead uses a top 5 and a jury.
  - ([2024 Reviewing](https://junctionhq.notion.site/Participant-Guidebook-Junction-2024-10559a11813780389e0fc382f7ec6ea8))

### Prizes
- **[2026]** €100,000 total, with "Full prize breakdown coming soon". It is still **UNVERIFIED** how the money splits between the main prize and challenge prizes.
  - Google DeepMind has "something special planned for the winning teams" ([YouTube "Junction 2026 x Google DeepMind"](https://www.youtube.com/watch?v=veBK-eczAPM)).
  - Tech partners give credits, and some award prizes for the best use of their technology.
- **[2025]** pool of €50k or more, with a €10k grand prize.
- **[2024]** €20k for the top 5: €10k, €5k, €2.5k, €1.5k and €1k.

### Tracks, partners, credits, mentors [2026]
- **Tracks** ([site](https://2026.hackjunction.com/#tracks)):
  - Hardware Track (Arduino)
  - Healthcare
  - AI Infrastructure (Verda)
  - FinTech
  - Agentic AI
  - Data

  "Tech challenges" from tech partners run across every track, and any team can take them alongside its track. The full challenge briefs are not public; they are revealed at the opening (challenge videos).
- **Partners**, as parsed from the site:
  - **Main:** Google DeepMind, Arduino, Verda.
  - **Challenge/major:** Hostinger, Valio Aimo, S-Pankki, Aalto University, Cala, City of Espoo, Exa, MariaDB. Also listed, tier unclear: AfterQuery, Bahn Express, AstraZeneca, Stoa, Intel, Context.dev, Rokoko, Ignite Next, Meta, Tieto.
  - **Tech partners:** OpenAI Codex, NVIDIA, Featherless, Modal, Qualia, CRACI, Atech.dev, Scailab, IronShard, Cloudinary, Wendy, Aiven, Oxylabs.
  - **Supporters:** MLH, Lifeline Ventures, Wave Ventures, FR8, Founders House, Aaltoes, AROC.
- **Credits/APIs:**
  - "Companies provide credits to their platforms." In 2024 these came as a **Hackerpack** on the Junction Platform.
  - The specific 2026 credit amounts (Modal, OpenAI Codex, Featherless, Verda GPU and so on) are **UNVERIFIED**; check the platform and the workshops.
  - Workshops run by DeepMind, Verda, Arduino, Cala, Modal, Exa, Context, Kiuas and Ignite Next.
- **Hardware Lab by Arduino (5th floor):** Arduino UNO Q boards, components, 3D printers, LeRobot arms and hardware mentors.
- **Mentors:** partner representatives on the floor throughout the event, plus hardware mentors. There is no public mentor booking system for 2026 (UNVERIFIED).

### Provided / bring
- **Venue:** open 24 h for the full 48 h. There are **no sleeping areas** [2026]; book a hotel to sleep properly.
- **Food:** dinner Fri, lunch and dinner Sat [2026 schedule]. There are refreshment sponsors (Valio, Nestlé, NOCCO, Elovena, …). The 2025 schedule also had breakfasts, and Sunday brunch at 11:00.
  - 2024 had free food on all three days, snacks, coffee and energy drinks, and **tap water only**, so bring a bottle [2024].
- **Showers:** 2026 is UNVERIFIED. In 2024 Dipoli had a rooftop sauna with a shower that had to be booked [2024].
- **Wi-Fi:** provided [2024].
- **Packing list [2024]:**
  - valid ID
  - laptop, charger, ethernet cable, headphones, and an EU plug adapter if needed
  - a change of clothes
  - toiletries and a towel
  - a water bottle

  Junction does **not** provide screens, mice, keyboards or headphones.

### Code of conduct
- The 2026 site links the [MLH Code of Conduct](https://static.mlh.io/docs/mlh-code-of-conduct.pdf); MLH is a partner.
- Terms §8.1: be respectful; harassment or discrimination means removal or disqualification. Illegal substances are banned at the venue (§8.5).
- In 2024, named harassment contacts wore armbands and were introduced at the opening [2024].

### Communication
- **Discord:** "Junction Community" server, about 4,800 members. The site links [discord.gg/nDgvafhRU4](https://discord.gg/nDgvafhRU4) and the platform links discord.gg/Rv4DyHpwkJ; both invites resolve to the same server, checked via the Discord API on 2026-11-10.
  - Announcements and questions to organisers go through #announcements, based on the 2024 practice.
- **Junction Platform dashboard:** check-in, team, submission and review all run through it, so remember your login [2024 practice]. In 2026 judging is "on the Junction Platform".
- Email: hello@hackjunction.com.

### Open gaps
- The 2026 submission form fields, including whether a video is required, its maximum length and the deck format: check the platform on Friday.
- The prize split between the main prize and each challenge, and the DeepMind "special" prize.
- Full challenge briefs and per-challenge judging criteria. Tracks are named, but the briefs come out at the opening.
- Credit amounts per tech partner; showers or sauna at Hype; breakfast on Sat/Sun; partner hotel names.
- How the MIT-licence statement in the FAQ fits with the Terms on IP.

---

# 2. Challenges, partners and past winners


Research date: 2026-11-10, three days before the event. **UNVERIFIED** marks claims backed by a single secondary source or by inference. Sections A and B cover 2026 only. Sections C to E cover past years and the patterns drawn from them.

**Main finding: the 2026 challenge briefs are not public yet.** On the Junction Platform, the public event payload for `junction-2026` has `"challenges":[]` ([hackjunction.app/hackathons/junction-2026](https://hackjunction.app/hackathons/junction-2026)). The official `llms.txt` (updated 16 Sep 2026) says: "Challenge tracks and the full pre-event programme are not announced yet. Say so rather than guessing" ([2026.hackjunction.com/llms.txt](https://2026.hackjunction.com/llms.txt)). The public challenge archive also has no 2026 entries. That archive is the JSON embedded in the [hackjunction.com](https://www.hackjunction.com/) bundle and served at `/challenges`: 147 challenges across 2017–2025. The platform has a "Challenges" tab with "main" and "tech" challenge lists, but only logged-in, accepted participants can see it. The briefs are expected there and in the challenge videos at the opening ceremony on Fri 13 Nov at 18:00.

---

### A. Junction 2026: confirmed facts

| Item | Fact | Source |
|---|---|---|
| Dates / venue | 13–15 Nov 2026, Hype Areena, Kivenlahti, Espoo (Vanha Jorvaksentie 3; end of the metro line). Junction Week pre-events from Mon 9 Nov | [2026.hackjunction.com](https://2026.hackjunction.com/), [llms.txt](https://2026.hackjunction.com/llms.txt) |
| Theme | "European Tech Renaissance": "Someone will move the center of gravity" (Copernicus framing) | [hackjunction.app](https://hackjunction.app/hackathons/junction-2026) |
| Scale | About 2,000 builders from 100+ countries; 3,542 registrations on the platform | 2026 site; platform payload `participantCount` |
| Prizes | €100,000 total; "full prize breakdown coming soon" (not yet published). DeepMind: "something special planned for the winning teams" | [2026 site](https://2026.hackjunction.com/), [YouTube: Junction 2026 x Google DeepMind](https://www.youtube.com/watch?v=veBK-eczAPM) |
| Team size | 1–4 (2025 allowed up to 5) | llms.txt, platform |
| Licence | "Submissions are open-sourced under the MIT licence … with the authoring team credited" | [llms.txt](https://2026.hackjunction.com/llms.txt) |
| Focus | "Most of the 2026 challenges center on AI"; three kinds of build: AI (models, agents), software, physical AI/hardware. The platform also lists sustainability, fintech, health, defence and quantum | llms.txt, platform |
| Hardware Lab (new) | By Arduino, on the 5th floor: Arduino UNO Q boards (Linux plus real-time MCU), components, 3D printers, LeRobot arms, hardware mentors. NVIDIA Jetsons are also reported (**UNVERIFIED**: search snippet of an organiser post) | 2026 site |

#### Tracks (official list, as named on the site; no briefs yet)
| Track | Track owner shown on the site | Likely challenge partners (**UNVERIFIED** mapping, inferred from partner type) |
|---|---|---|
| Hardware Track | **Arduino** | Arduino, Intel, Rokoko (mocap), Ignite Next, Qualia, Atech, Scailab, Meta |
| Healthcare Track | — | AstraZeneca |
| AI Infrastructure Track | **Verda** (formerly DataCrunch, Helsinki GPU cloud) | Verda, Modal, NVIDIA, Featherless |
| FinTech Track | — | S-Pankki, Cala |
| Agentic AI Track | — | AfterQuery, Exa, Context.dev, Hostinger |
| Data Track | — | MariaDB, Valio Aimo, Oxylabs |
| Tech challenges (cross-track) | Run across every track: "Companies provide credits to their platforms, and some of them award prizes to the best use cases" | — |

Source: [2026.hackjunction.com](https://2026.hackjunction.com/) (#special, #partners sections).

#### Partners (from the 2026 site partner wall, fetched 2026-11-10)
- **Main partners:** Arduino, Verda.
- **Challenge partners:** Hostinger, Valio Aimo, S-Pankki, Aalto University, Cala, City of Espoo, Exa, MariaDB, AfterQuery, Bahn Express, AstraZeneca, Stoa, Intel, Context.dev, Rokoko, Ignite Next, Meta, Tieto.
- **Tech partners:** OpenAI Codex, NVIDIA, Featherless, Modal, Qualia, CRACI, Atech.dev, Scailab, IronShard, Cloudinary, Wendy, Aiven, Oxylabs.
- **Special partner:** Google DeepMind. It gives the opening keynote and a workshop, and has a prize for the winners still to be announced.
- **Supporters:** Lifeline Ventures, Wave Ventures, FR8, AROC (Aalto Robotics Club), Thinkin' Rocks, Founders House Helsinki, MLH, Aaltoes, XR Creator Con. MLH x GitHub run a session.

#### Workshops (signal which partner APIs will matter)
| Day | Time and workshop |
|---|---|
| Fri | 20:15 DeepMind · 20:45 Verda · 20:45 Arduino · 21:15 MLH x GitHub |
| Sat | 11:15 Cala · 12:15 Ignite Next · 13:00 Hostinger keynote · 13:45 Modal · 14:50 Kiuas · 16:45 Exa · 17:45 Context |

#### Schedule and deadlines
| Day | Times |
|---|---|
| Fri | Doors 16:00; opening plus challenge videos 18:00; hacking 19:30; **preliminary submission 23:59** (platform says 23:55) |
| Sat | Submissions open 12:00 |
| Sun | **Final submissions 10:00**; review 10:30–13:00; final ceremony 14:00; challenge winners 15:10; Junction winner 15:50 |

#### Judging (official)
1. Each Challenge Partner picks its own track winners against its own criteria.
2. The main prize starts with **face-to-face peer review**: teams judge each other in person, which selects the **top 5**.
3. The top 5 pitch live on stage, and a **grand jury of 7** picks the winner.

Source: [2026 site #judges](https://2026.hackjunction.com/).

#### Grand jury: stated criteria (quote these in the pitch)
| Judge | What they say they look for |
|---|---|
| Kia Kanninen (CEO, Founders House Helsinki; ex-Slush startup team) | "Anyone can vibe code almost anything … teams that start from a **problem worth solving**, not just a feature that's easy to build." |
| Daksh Raghuvanshi (RL Lead, AfterQuery) | Teams that "can explain exactly **why an agent fails** in their world, and whose **reward holds when someone tries to break it**." This is an agent-evaluation and RL-environment lens; AfterQuery is also a challenge partner. |
| Otto Söderlund (AI Lead, Supercell; Speechly founder) | "Start from a **real user problem** and ship something people want to **come back to**." |
| Timo Ahopelto (Lifeline Ventures) | VC lens; no stated criterion (investor-grade impact assumed). |
| Umar Noor (Google DeepMind, Developer Experience) | No stated criterion; GTM role ("prototype to real-world impact using AI"). |
| Two judges | To be announced. |

#### 2026 claims not verified
- A LinkedIn search snippet attributed to a recruiter or organiser says "there will not be an LLM challenge at Junction 2026 (yet)" (**UNVERIFIED**; it conflicts with llms.txt "most challenges center on AI" and with an "Agentic AI Track").
- A Verda October digest lists "Junction – November 14–16th", which is the wrong dates ([verda.com blog](https://verda.com/blog/verda-datacrunch-monthly-digest-october-edition)).

---

### B. Junction 2026: per-challenge table

| Partner | Challenge title | Problem | Data/APIs/HW | Criteria | Prize | Source |
|---|---|---|---|---|---|---|
| *All 2026 partners* | **Not published** | — | — | — | — | Platform `challenges: []`; llms.txt |

**Action:** take the briefs from the Junction Platform "Challenges" tab, or from the opening-ceremony videos, as soon as they appear. The DeepMind workshop and keynote and the Verda workshop come first (Fri 20:15–20:45), so they will reveal those tracks first.

---

### C. Past editions (Helsinki/Espoo main event)

**Warning on the archive's year labels.** The year labels in the official challenge archive are off by one for many entries. Entries labelled "2025" include challenges from the Junction 2024 event: Fingrid, KONE x Granlund, HKFoods, Peikko, Sitra, Huawei 3D UI and Aava ThriveConnect. This is confirmed by the archived 2024 event API ([web.archive.org snapshot](https://web.archive.org/web/20241229041740id_/https://eu.junctionplatform.com/api/events/public/junction-2024)) and by [BHOS](https://www.bhos.edu.az/en/news/2552). Entries labelled "2024" (Outokumpu, TietoEvry PainMgmt) are really 2023 ([marincomics](https://marincomics.com/junction-2023.html), [Tieto 2023 page](https://www.tietoevry.com/fi/tapahtumat/2023/junction-2023)). Entries labelled "2023" look like 2022: the Aiven text says "At Junction 2022". The years below are corrected.

#### Junction 2025, "Utopia & Dystopia" (14–16 Nov, Hype Areena, Espoo)
- About 1,500 hackers, 111 nationalities, 291 projects, 40+ partners. Prize pool €50k+, grand prize €10k; 2nd overall got €7.5k. Teams of up to 5. Peer review (Gavel) chose the top 5, which pitched on stage.
- Sources: [platform](https://hackjunction.app/hackathons/junction-2025), [Aalto](https://www.aalto.fi/en/news/aalto-students-and-researchers-shape-together-how-we-age-with-ai-at-junction-hackathon-2025), [Frank Sandqvist story](https://www.hackjunction.com/blog/frank-sandqvist-story).

**Challenges** (from the archive, [hackjunction.com/challenges](https://www.hackjunction.com/challenges); first four previewed in [sneak-peek blog](https://www.hackjunction.com/blog/sneak-peek-partner-challenges)):

| Partner | Challenge | Data/HW given | Criteria (abridged) | Prize |
|---|---|---|---|---|
| Sensofusion (main partner) | *Radio City*: visualise radio propagation in a 3D city | Hong Kong 3D model (JAXA/OSM), Python helper | "Make it flashy. Wow us", plus clarity, credibility, polish | DJI Mini 3 per member |
| Sensofusion | *Lights, Camera, Reaction!*: event-camera vision | On-site pro event cameras, APIs | Accuracy, creativity, real-time | DJI drones |
| Supercell | *AI-First Fun*: original game shaped by AI | Mentors, any tools | — | €3k/2k/1k |
| Wolt | AI for the next local experience | — | User/market impact, novelty, AI depth, scalability | €2k/1.5k/500 |
| Valmet x HSY | *Intelligent Flow Optimization*: multi-agent wastewater pumping | Years of real HSY inflow data, OPC UA, digital twin | Agent coordination, OPC UA realism, technical soundness | €2k/1.5k/500 |
| Valio Aimo | *Zero-Fail Logistics*: predict missing items, voice-first customer care | Real order and picking data plus mock extracts | Production-ready feasibility, end-to-end coverage, AI/CX quality, FTE savings; "strong demos considered for real development" | €2k/1.5k/500 |
| WithSecure | *Reputation Recon*: product name to a CISO trust brief with sources | App list, CVE/CVSS refs | Evidence quality, entity resolution, transparent scoring, resilience | €2k/1.5k/500 |
| Pfizer x Aava | *Head Start*: forecast migraine onset | Fact sheet; wearable, calendar and sleep signals suggested | **Usability 50%**, feasibility 25%, originality 25% | €2k/1k/500 |
| Aalto University | *Aging with AI* | Mentors (HCI, aging research) | Impact, feasibility and ethics, implementation | €2k |
| Fortum | *Watt's next?*: energy consumption forecasting | Consumption dataset | **Accuracy 100%** gate (top 10), then bonuses | €3k pool |
| Suomen Pankki (Bank of Finland) | Use AI to develop regulation | 55 GB of real legislation, GCP | Innovation, repeatability, architecture (40%), risk coverage | €1k/600/400 |
| Traficom | *AI Audit Aid* | Mentors | Impact, feasibility, innovation, reproducibility | €1.5k/1k/500 |
| P&G (Pampers) | *CTRL+C, CTRL+Campaign*: campaign automation | Braze API, mock data | Effort reduction, AI personalisation, scalability | €3k |
| Harvia | *Sauna Intelligence* | Sauna sensors in venue saunas, GraphQL API | Function, creativity, business potential, **use of AI coding tools** | €1.5k plus €1.5k 30-day follow-up |
| Denso | *ChargeID*: EV charging with decentralised ID | DID stack, mentors | Innovation, usability, privacy | €1k total |
| City of Espoo | Business Advisory Service 2.0 | Mentors | Clarity, UX, impact | €750/500/250 |
| Univ. Helsinki Education Hub | Financial literacy for all | Research summaries | Educational effectiveness, research-informed design | 1.5k/500/500 |
| Figma | Figma Make challenge | Figma Make access | How Make accelerated the workflow | €3k |
| Snap | Spectacles AI×AR companion | Spectacles gen 5, Lens Studio | Six criteria, incl. visual quality | Spectacles |
| Tech side challenges | Google Cloud, SAS, ElevenLabs, n8n, Starstuff, Featherless | Credits | "Best use of X" | Swag or credits |

Other 2025 sponsors: Verda (DataCrunch), OpenAI, Linear, JetBrains, Vaadin, MLH.

**2025 winners**

| Place | Team / project | What it built | Why it won (evidence) |
|---|---|---|---|
| 1st overall (€10k) | **WAVELET** (Manna, Juneja, Czirjak, Alluri) | Real-time GPU EM simulation (Maxwell's equations, compute shaders, C++/OpenGL) over a Hong Kong 3D city. It also won the Sensofusion *Radio City* track. [GitHub](https://github.com/ron0studios/WAVELET) | Hard, real tech with a visually spectacular live demo, matching a brief that literally said "wow us" |
| 2nd overall (€7.5k) | **LoreDash** (Frank Sandqvist, solo) | Multiple AIs generating a minigame per Wikipedia article. Also a track runner-up | Fun, polished, entertaining presentation ([blog](https://www.hackjunction.com/blog/frank-sandqvist-story)) |
| Top 5 | **DroneStalker** | Drone detection (YOLO) plus an LSTM trajectory predictor (claims 50.3% better than the FRED baseline); cleaned a 200 GB dataset to Hugging Face; game-like web mission with a Gemini "Commander" and ElevenLabs voice. Likely the Sensofusion event-camera brief (**UNVERIFIED**). [codya.dev](https://codya.dev/project/2511-junction) | Measurable result against a baseline; interactive experience that people "experienced, not just saw" |
| Top 5 | **Walkthrough** (Wolt challenge) | — | [Pitch video](https://www.youtube.com/watch?v=9KT34TKEBJ0) |
| Top 5 | **λpump** (HSY & Valmet challenge) | Wastewater pump optimiser on real data | [Pitch video](https://www.youtube.com/watch?v=8yl6ji8T0lc) |
| Aalto track | **ApprenticeCircle+** (Tommin Teekkarit) | Voice-first platform pairing older adults with young people; profile created by phone call | Stood out among about 30 submissions for its social insight and thoughtful prototype ([Aalto](https://www.aalto.fi/en/news/aalto-students-and-researchers-shape-together-how-we-age-with-ai-at-junction-hackathon-2025)) |

#### Junction 2024, "Back Offline" (8–10 Nov, Kaapelitehdas, Helsinki)
- 1,000+ participants, 80+ nationalities, 211–250 projects. Fully in-person.
- Top 5 shared €20k: €10k / 5k / 2.5k / 1.5k / 1k. Peer review (`gavelPeerReview`), then manual finals selection of 10 finalists.
- Sources: [archived event API](https://web.archive.org/web/20241229041740id_/https://eu.junctionplatform.com/api/events/public/junction-2024), [BHOS](https://www.bhos.edu.az/en/news/2531).

**The 9 challenges**

| Partner | Challenge | Criteria / prize |
|---|---|---|
| KONE x Granlund | Modernizing a trillion-euro inventory (building equipment inventory) | Usability, automation of manual steps; €3k |
| KONE | BIM for any building, by anyone (gamified 3D modelling) | Ease of use; React/Python/Java preferred; €3k |
| Fingrid | Empowering Development Transparency (Datahub release info) | UX focus; €1.5k/500 |
| HKFoods | ZeroWaste Factory (under- and overweight products) | Proactive prevention; €500 per person |
| Huawei | Creative 3D UI Apps (Graphics SDK) | Real-time on Windows, +1 on HarmonyOS; €4k/2k/1.5k |
| Peikko | IFC Innovate (construction) | Innovation, IFC use; €2k |
| Sitra | Digital democracy tools | "Easy, ready to use … integrated to the real world"; €2k/1k |
| Aava | ThriveConnect (work well-being matching) | Creativity, effectiveness; €2k/1k |
| Aalto University | Sustainable Space Data | Sustainability plus two more criteria |

**2024 winners**

| Place | Team / project | What it built and why it won |
|---|---|---|
| 1st overall (€10k) | **BREAKDANCE** (Frank Sandqvist, solo) | "AI-driven inventory management app that gamified equipment reporting"; Next.js with a DXF-to-SVG floor-plan server. Probably the KONE x Granlund inventory challenge (**UNVERIFIED**). He credits "an engaging AI-generated rap video" in the pitch. [GitHub](https://github.com/FrankSandqvist/junction-2024-breakdance), [blog](https://www.hackjunction.com/blog/frank-sandqvist-story) |
| Fingrid track winner | **Aligned** (team Evergreen, BHOS) | Central platform for B2B customers to track releases, requirements and milestones; €1.5k ([BHOS](https://www.bhos.edu.az/en/news/2552)) |
| HKFoods, 2nd of about 200 (overall or within the track unclear, **UNVERIFIED**) | **Sonaptics** (Taito United) | Contactless gesture communication for hygiene-sensitive factory lines: React, Python, WebSockets, motion sensors, real hardware. The challenge was chosen after talking to the partner in person ([Taito](https://www.taitounited.fi/en/blog/menestyst%C3%A4-junction-hackathonista/)) |

#### Junction 2023 (10–12 Nov, Kaapelitehdas, Helsinki)
- 1,500+ participants; main prize €20k; about 230 submissions. The platform crashed during submission and peer voting.
- Sources: [Kaapelitehdas](https://www.kaapelitehdas.fi/en/events/junction-2023/), [marincomics](https://marincomics.com/junction-2023.html).

**Challenges** (archive, re-dated):

| Partner | Challenge | Criteria / prize |
|---|---|---|
| Outokumpu | Sustainable GenAI assistant for insights | Trustworthiness of results, output quality; €2k/1k/500 |
| Huawei | *Sense the Motion*: wearable features to cut sedentary behaviour | 2-minute demo video required; **€8k/5k/3k**, the largest partner prize seen |
| TietoEvry | *PainMgmt*: non-opioid pain management | Code quality, innovation, presentation; Polar watches |
| Pixieray | *Peek Behind the Eyes*: eye-tracking glasses data | Working software or live data; €500/300/100 |
| Aalto University | Resource Revolution, now (critical raw materials) | Innovation, impact; €1k |
| Aalto University | Energy Revolution, now | Same criteria; €1k |

**2023 winner:** "Driving Change – In the Blink for Safety" (Andersson, Enberg, Granlund, Peltola), per the Wikipedia list (**UNVERIFIED**: a single secondary source, no project description found) ([Wikipedia](https://en.wikipedia.org/wiki/Junction_(hackathon))).

#### Older reference points (one line each)
- **2022:** Wolt (Drive API, sustainability), green-coding challenge (scored 4×25 points on energy efficiency), Aiven and Google Cloud side challenges. Archive-labelled "2023" but probably 2022: BNB Chain, Cronvall, Smartly.io, and Veikkaus (WebGPU). Main winner: *Bitter Sweet* (Wikipedia).
- **2017:** "A mix of machine learning and cool UX won Junction 2017" ([Medium](https://medium.com/hack-junction/a-mix-of-machine-learning-and-cool-ux-won-junction-2017-15963c0ace3b); the page returned 403, so only the title was verified).
- **Repeat winners:** one trio won twice ([Medium](https://medium.com/hack-junction/this-trio-has-hacked-the-hackathon-ville-andreas-and-teemu-won-junction-for-the-2nd-time-b193e9d7f7b); page returned 403).

---

### D. Patterns

#### Returning partners
| Partner | Years seen | Note |
|---|---|---|
| **Aalto University** | 2023, 2024, 2025, 2026 | Every year. Societal themes (energy, resources, space, aging); about €1–2k; criteria impact, feasibility, ethics |
| **Valio Aimo** | 2025, 2026 | Real order and picking data; production-minded judging ("path to production") |
| **City of Espoo** | 2025, 2026 | Public-service UX; clarity first |
| **Verda (DataCrunch)** | 2025 sponsor, 2026 main partner | GPU cloud; owns the AI Infrastructure track |
| **Featherless, OpenAI, MLH** | 2025, 2026 | Credits and tech challenges |
| **Tieto(Evry)** | 2023, 2026 | Health in 2023 |
| **Huawei** | 2023, 2024 | Big prizes; absent in 2026 |
| **Aava (± Pfizer)** | 2024, 2025 | Health and well-being; 2026 health now AstraZeneca |
| **Wolt, Google Cloud, Aiven** | 2022, then 2025/2026 | Intermittent |
| **Supercell** | 2025 challenge; 2026 AI lead is on the jury | — |
| **Sensofusion** | 2025 main partner | Absent from the 2026 list |

#### Recurring themes
- AI and agents applied to an operational process. Since 2023 the "AI" share has grown each year, and in 2026 it is explicitly the majority.
- Energy and grid: Fingrid, Fortum, Valmet/HSY, Aalto Energy.
- Health and well-being: TietoEvry, Aava, Pfizer, and AstraZeneca in 2026.
- Built environment and industry: KONE, Granlund, Peikko, Outokumpu, HKFoods.
- Public sector and regulation: Sitra, Bank of Finland, Traficom, Espoo.
- Logistics: Wolt, Valio Aimo.
- New in 2026: hardware and physical AI (Arduino lab), AI infrastructure (Verda), and FinTech as a named track (S-Pankki, Cala).

#### Rubric patterns across about 30 recent partner rubrics
- **Feasibility and real-world adoption** appear in nearly all rubrics: "production-ready", "could be integrated straight away", "path to production".
- **UX and usability** are often weighted heavily: Pfizer weights usability at 50%, Fingrid is UX-only, Espoo says "a simple, clear solution often beats a complex one".
- **Use of the partner's own data, API or hardware** is often a hard requirement: Huawei SDK, Braze, OPC UA, Harvia sensors, event cameras.
- **Measurable outcome:** some rubrics score a metric. Examples are forecast accuracy as a gate at Fortum, FTE savings at Valio Aimo, and an energy-efficiency metric in 2022.
- **Explainability and transparency:** evidence and sources (WithSecure), transparent scoring, reproducibility (Traficom, Bank of Finland).
- **Wow and polish:** Sensofusion and Snap explicitly score visual quality.

#### What winners have in common
1. **A live, visual demo of something technically real.** WAVELET ran a GPU physics simulation; DroneStalker trained a model and beat a published baseline.
2. **Real partner data or hardware, used for a measurable result.** λpump used HSY data; DroneStalker used a 200 GB dataset; Sonaptics used physical sensors.
3. **Pitch as entertainment.** Frank Sandqvist won twice with a "clean and realistic" product presentation, one of them with an AI-generated rap video; DroneStalker gave a game-like interactive mission with voice.
4. **One problem done end-to-end beats breadth.** Winners are often solo or small teams with a single sharp idea.
5. **They talked to partner reps early.** Sonaptics switched challenge after talking to HKFoods, and partners mentor the work through the weekend.
6. **A two-level game.** The track prize depends on the partner's rubric. The main prize depends on peer review, where other hackers spend about 2 minutes per project, and then the stage pitch. A project needs to be instantly legible and impressive to peers to reach the top 5.

---

### E. Tips for a 4-person team using AI coding agents (Junction 2026)

- **Pick the track at 18:00 Friday.** Choose a challenge with a rubric you can score on, real data or hardware, and a partner present on site; talk to the partner reps in the first hour. Preliminary submission is due at 23:59 Friday, so register the project then.
- **Speak the jury's language.** Kanninen: the problem matters more than the feature, so "vibe-coded features" lose. Raghuvanshi: show where the agent fails and how the evaluation or reward resists gaming, so put an eval harness and a failure-case slide in any agentic project. Söderlund: show retention or "come back" value.
- **Agents give breadth; humans must give depth and the demo.** Use agents for scaffolding, data wrangling and UI. Spend human time on the one hard technical core: a model, simulation or measurable metric versus a baseline, as WAVELET and DroneStalker did.
- **Suggested roles:**
  - 1 person owns the partner relationship, the rubric and the pitch (start the deck and video Saturday afternoon; marincomics' lesson is not to leave it to Sunday).
  - 2 people build the core plus integration. Integrate by Saturday evening at the latest; Sonaptics only just made it.
  - 1 person builds the demo surface and the visuals: a screenshot-rich project header, a 2-minute video, and a deployed URL.
- **Stack one partner track and one or two tech challenges** (DeepMind/Gemini, Modal, Featherless, Exa, Context, Cloudinary, Aiven) that fit naturally. Each tech challenge is an extra prize lottery at low cost.
- **Hardware is the differentiator in 2026.** A whole floor, UNO Q, LeRobot arms and 3D printers are available. Physical demos stand out in peer review, but book bench time early and keep a software-only fallback.
- **Make it measurable.** Put one number on the slide: accuracy versus baseline, minutes saved, or FTE saved.
- **The submission is MIT-licensed and public**, so don't paste secrets or partner data into the repo.
- **Plan for platform outages.** The platform crashed in 2023, so keep the video and deck on a separate host.
- **Final submission is 10:00 Sunday, with no extension.** Freeze features at about 06:00 and rehearse the 2-minute peer-review pitch and the stage pitch.

---

### Open gaps
- No 2026 challenge titles, briefs, datasets, rubrics or prize split are public. Only the platform, behind login, or the opening ceremony will reveal them.
- The 2026 track-to-partner mapping is inferred except for Arduino (Hardware) and Verda (AI Infrastructure).
- What Google DeepMind's "something special" prize is.
- Two grand-jury members are not yet announced.
- 2023 winner details, and Walkthrough's project content, are not found.
- Could not read the Medium pitching guide, the 2017 and repeat-winner posts (all returned 403), the IEEE 9453857 paper (empty page), or the Notion 2024 Challenge Intros (JS page, not attempted in depth).

---

# 3. Team Hour49 and our prep

Moved on 2026-11-10 to [../05-team/hour49.md](../05-team/hour49.md): team and roles, the prep repo and its agent workflow, the team website, decisions and open tasks.
