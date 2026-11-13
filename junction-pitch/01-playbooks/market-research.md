# Hackathon-speed market and problem research: playbook for Junction 2026 (Hour49)

Compiled 2026-11-10 for the research and marketing lead. Event context comes from `00-event/junction-info.md` (sections 0, 2D, 2E). Sources are inline. Items marked **UNVERIFIED** come from a single or secondary source; check them before putting them on a slide.

**What this research must produce for the pitch.** Partner rubrics nearly always score feasibility, real-world adoption, UX and, sometimes, a metric (Fortum's forecast accuracy, Valio Aimo's FTE savings). The grand jury asks for "a problem worth solving, not a feature" (Kanninen), a "real user problem" that people "come back to" (Söderlund), and "why an agent fails" (Raghuvanshi). Peers in the face-to-face review give each project about 2 minutes. So the research needs to deliver five things:
1. **One specific user**, who must be specific enough that a judge can repeat it.
2. **One sourced pain number**: time or money lost, an error rate, or the number of people affected.
3. **One sentence on why the alternatives fall short**, including doing nothing.
4. **One honest market number**, bottom-up, with its assumptions shown.
5. **One one-liner.**

Everything else is backup for Q&A.

---

## 0. Ground rules (apply to every section)
- **Time-box it hard.** Total research effort is about 6–8 person-hours over the weekend, front-loaded on Friday night. If a step overruns its box, ship the "good enough" version and move on.
- **Read the rubric first.** The partner's rubric tells you which research matters. If the rubric says "impact on X", find the X number first. One judge's guide puts it this way: the rubric tells you what organisers will reward, so read it before the problem statement ([JetBrains, "notes from the judging table", 2026](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/); 403 on fetch, quoted from the search summary).
- **The partner rep is your best source.** Junction partners bring real data and mentor all weekend. Sonaptics switched challenge after talking to HKFoods (junction-info §2D). One conversation with a partner gives you more evidence than an hour of desk research.
- **Keep a source log from minute one.** Create `03-research/sources.md` with one line per fact:
  `claim | number | unit | year | geography | source title | URL | accessed | primary/secondary | confidence`.
  Every number on a slide must trace back to a line there.
- **Research serves the demo, not the other way around.** A judge's year of notes found that the teams who opened with "market context, personal stories or problem statements" lost time before the product appeared. Strong teams opened with what the tool does and for whom ([Kurbaitaev, DEV, 2026](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)). Use the research for one slide and for Q&A, not for a five-slide preamble.

---

## 1. Competitor and similar-ideas scan (about 60–90 min, Fri night; refresh 20 min Sat)

### 1.1 Why do it at all
- **To avoid rebuilding a known project.** Peers and partner judges have seen past Junction projects, so a near-duplicate costs you novelty points.
- **To find the gap.** Dunford's positioning starts with the **competitive alternatives**, "what would the customer do or use if my product didn't exist?" Those alternatives are often things that don't look like competitors, and "doing nothing" is often the biggest one ([April Dunford positioning, summarised in MTP/BoS talks and templates](https://www.mindtheproduct.com/everything-has-changed-except-for-the-fundamentals-of-positioning-april-dunford-at-mtpcon-london-2026); [Miro template](https://miro.com/miroverse/april-dunfords-positioning-template); wording **secondary**, check against *Obviously Awesome* before quoting).

### 1.2 Where to look, in order of yield per minute
| # | Source | What it gives | How to search fast | Limits |
|---|---|---|---|---|
| 1 | **Partner rep plus the challenge brief** | The partner's current internal tools and vendors: the real status quo | Ask "What do you use today? What did you try that failed?" | It's verbal, so note who said it and when |
| 2 | **Junction challenge archive** [hackjunction.com/challenges](https://www.hackjunction.com/challenges) | 147 challenges from 2017–2025, with rubrics and prizes (per junction-info §0.1/2C). The page renders in JS, so open it in a browser | Filter by the same partner (Valio Aimo, Espoo, Aalto and TietoEvry recur) and read last year's brief and winner | The archive's year labels are off by one (junction-info §0.1) |
| 3 | **Past Junction winners and project galleries** | What already won for this partner; what peers have seen | junction-info §2C; Junction platform projects; search `"Junction 2025" <partner> site:github.com` and LinkedIn posts | Galleries are not fully public |
| 4 | **Devpost** [devpost.com/software](https://devpost.com/software) | Hackathon projects worldwide, with "built with" tags | Search `devpost.com/software/search?query=<keyword>`, then a hackathon's own "Project gallery" tab, which has a filter ([DeveloperWeek gallery example](https://backiee.wasmer.app/https_developerweek-2024-hackathon_devpost_com/project-gallery)) | Search depth unverified; skim titles and taglines only |
| 5 | **GitHub** | Open-source tools that solve the core | `github.com/search?q=<keyword>&type=repositories`, sorted by stars; check topics pages | Stars aren't adoption |
| 6 | **Product Hunt** [producthunt.com](https://www.producthunt.com) | Launched consumer and SaaS tools plus user comments, which are free pain evidence | Search the keyword; read the top comments for complaints | Skews toward US/SaaS |
| 7 | **YC directory** [ycombinator.com/companies](https://www.ycombinator.com/companies) | Funded startups on the same problem; also proof the problem is fundable | Free to browse, with filters by batch, industry, status, region and size ([YC blog](https://www.ycombinator.com/blog/the-yc-directory)) | US-centric |
| 8 | **Crunchbase (free)** | Funding and headcount for 2–3 named competitors | Look up named companies only | Free plan reported at about 5 results per search and few profile views (**UNVERIFIED**: [ZoomInfo](https://pipeline.zoominfo.com/sales/crunchbase-pricing), [roundfunded](https://www.roundfunded.com/en/alternatives/crunchbase)) |
| 9 | **Dealroom** [dealroom.co](https://dealroom.co) | European and Nordic startups (useful for "who does this in Finland") | Basic company pages are public via search; the free tier is unclear | Sources conflict on the free tier ([Dealroom blog on free vs paid](https://dealroom.co/blog/searching-filtering-companies-investors-important-changes-free-vs-paid-features)) |
| 10 | **App stores and G2/Capterra** | Incumbent apps and B2B tools, and **1–2-star reviews**, which are quantified pain in users' own words | Search the category; sort reviews by lowest rating; note recurring complaints | Reviews are anecdotal; quote them, don't count them |
| 11 | **AI-tool directories** (There's An AI For That, Futurepedia) | "Is there already a GPT wrapper for this?" | Keyword search | Many listings are dead |

**AI-agent prompt (this step works well delegated):**
"List up to 12 existing products, open-source projects and past hackathon projects that address <job> for <user> in <EU/Finland>. For each, give the name, URL, type (direct, indirect or status quo), the target user, pricing if public, and one weakness relevant to <our differentiator>. Mark anything you could not open as UNVERIFIED. No invented companies."
A human then opens the top 5 URLs to confirm they are real. Hallucinated competitors are the main risk here.

### 1.3 How to classify the alternatives
| Class | Definition | Example (an agentic invoice-checking idea) |
|---|---|---|
| **Direct** | The same job, the same user, a similar approach | Another AI accounts-payable tool |
| **Indirect** | The same job done a different way, or a horizontal tool | An ERP module, an outsourced bookkeeper, generic ChatGPT |
| **Status quo / do nothing** | Spreadsheets, email, manual checks, accepting the loss | A clerk with Excel and a two-day backlog |
| **Partner's internal** | Whatever the challenge partner runs now | Partner rep tells you |

Rule: always include the status quo. Then quantify its cost in §4. That cost is the strongest "why switch" argument, and partner judges recognise it as their own reality.

### 1.4 Output formats (pick one for the deck; keep the table in backup)
**A. Comparison table (backup slide or README).** Use 4–6 rows and 4–5 columns, chosen from the rubric's own words:

| | Status quo (Excel and email) | Competitor A | Competitor B | **Us** |
|---|---|---|---|---|
| Works with partner's data X | ✓ manual | ✗ | ✓ | ✓ |
| Time per case | 20 min | 5 min | 8 min | **<1 min (measured in demo)** |
| Explains its decision | n/a | ✗ | partial | ✓ |
| Cost | staff time | €€€ | €€ | € |

Only claim what the demo actually shows. Any "✓" for us that isn't demonstrated is an overclaim a judge can puncture.

**B. A 2x2 positioning map (main deck, half a slide).** Pick two axes that matter to the user and on which we win **because of** what we built. Typical pairs are manual↔automated × generic↔domain-specific, or slow/batch↔real-time × black-box↔explainable. Put the status quo on the map. Avoid axes where "us" ends up in the corner by construction, because judges see that as a cliché.

**C. One-sentence "unlike" line** (Moore's second half, see §5): "Unlike <alternative>, we <key difference>."

---

## 2. Target user (about 45 min desk + 60 min talking, Fri 19:30–23:00, re-check Sat morning)

### 2.1 Fast persona: a proto-persona in 10 minutes
Don't write a marketing persona with a stock photo. Write a **one-card proto-persona** that names a real role:
- **Who:** role, context, frequency. Example: "Shift lead at a Valio Aimo picking warehouse, 30 pickers, night shift."
- **Job:** what they are trying to get done (JTBD, below).
- **Current workaround:** the status quo from §1.
- **Pain, in numbers:** from §4.
- **Trigger:** the moment they would reach for our tool.
- **Evidence:** who we talked to, plus one quote.

Specificity is itself the signal. A judge who scored three hackathons in 2026 notes that "Athletes" is not an answer to "who is this for?", while "a regional fighter with 40,000 followers and no manager" is. Specificity signals you talked to real people ([Kurbaitaev](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)).

### 2.2 Jobs to be done in one line
Use the job story format usually attributed to Intercom: **"When <situation>, I want to <motivation>, so I can <expected outcome>."** A common extension adds "…without <pain>" ([GrowthX copy of Intercom's template](https://growthx.club/template/intercoms-jtbd-template); [Slab](https://slab.com/library/templates/intercom-job-story/)). Write 3 job stories, rank them by pain × frequency, and build for the top one.

Optional: fill in the **customer side of the value proposition canvas** (jobs, pains, gains), ranking the top 3 in each. Then map **pain relievers and gain creators** to them. "Fit" means each reliever maps to a top pain ([Strategyzer VPC, via Auckland CIE PDF](https://www.auckland.ac.nz/assets/cie/innovation-resources/Value%20Proposition%20Canvas.pdf); [CERN Indico copy](https://indico.cern.ch/event/940005/sessions/415734/attachments/2334618/3979148/Value-Proposition-Canvas-Template-and-Guide-hd9tp7.pdf)). This takes 15 minutes on a whiteboard, and the right half of the canvas becomes the solution slide.

### 2.3 Validate inside the hackathon (ranked by value)
1. **Partner reps and mentors (essential; within the first hour after briefs).** They are the user, or they speak for the user, and they also judge the track.
2. **Domain people among the participants and staff.** Nurses, accountants or logistics workers are often hacking. Ask on Discord: "Anyone who has worked in <domain>? 5 min, coffee on us."
3. **Other hackers as proxy users.** Only use them for consumer or developer-tool ideas. They are also your peer-review judges, so it doubles as a test of whether the idea is legible to them.
4. **A quick survey (optional, Sat morning).** Use a Google Form with 3–5 questions and post it in Junction Discord and the team's networks. Treat it as directional. Don't claim n=23 is a market study.
5. **Online traces.** Reddit, forum threads and 1-star app reviews give quotable pain in the users' own words.

**Interview rules (the Mom Test).** Talk about *their* life, not your idea. Ask about specific past events, not opinions about the future. Listen more than you talk. Compliments are "fool's gold". A strong signal is when the person commits time, money or reputation ([summaries: Rekhi](https://www.sachinrekhi.com/the-mom-test-rob-fitzpatrick), [mtlynch](https://mtlynch.io/book-reports/the-mom-test/)).

The 5-question hackathon script (about 7 min):
1. "Tell me about the last time you had to <job>. What happened?"
2. "How long did it take? How often does it happen?" This gives you the numbers for §4.
3. "What do you use today? What's annoying about it?" This confirms the status quo from §1.
4. "What have you tried to fix it? What did it cost?"
5. Only at the end, show the mock or demo: "Would this have helped last time? What's missing?" Then the commitment ask: "Can we quote you or use your data? Will you come to our table Sunday?"

Log each conversation in `03-research/users/interviews.md` (who, role, date and time, 3 bullet facts, 1 verbatim quote, the commitment).

**Optional "come back" signal** for Söderlund's lens: ask testers the Sean Ellis question, "How would you feel if you could no longer use this?". The startup benchmark is 40% "very disappointed", but it needs 30 or more real users, so at a hackathon it is only anecdotal ([First Round on Superhuman](https://review.firstround.com/how-superhuman-built-an-engine-to-find-product-market-fit)). Use a quote, not a percentage.

### 2.4 Output format
One card, also used as the 15-second opening of the peer-review demo:
```
USER   Night-shift lead, 30-picker warehouse (Valio Aimo, Kerava)        <- talked to 2 (names in interviews.md)
JOB    When a picker reports a short-pick, I want to know if it's a stock error or a
       picking error, so I can fix the slot before the morning trucks leave.
TODAY  Walk to the shelf + check WMS screen + Excel log (status quo)
PAIN   ~15 min per incident, ~20 incidents/night (partner rep, Fri 20:40)
QUOTE  "Half my night is chasing ghosts in the system."
```
(The example is illustrative; replace it with real data.)

---

## 3. Market size (about 45 min, Sat morning; once the idea is stable)

### 3.1 What a hackathon jury needs
Partner judges care about adoption inside *their* company, so a partner-level number usually beats a global TAM. The VC on the jury (Ahopelto, Lifeline Ventures) will discount a top-down figure taken from an industry report. Sources consistently say investors trust **bottom-up** sizing more, because each assumption can be checked, and that a top-down figure alone is a red flag ([Stripe guide](https://stripe.com/resources/more/tam-sam-and-som); [LetaVC](https://medium.com/letavc/how-to-estimate-market-size-tam-sam-som-89ec3285e79c); [Waveup](https://waveup.com/blog/top-down-and-bottom-up-market-size-calculation); claims such as "2x more credible" are **UNVERIFIED** marketing statistics, so don't repeat them). Sequoia's classic deck outline asks for a TAM (top-down), a SAM (bottom-up) and a SOM ([Sequoia template, reproduced PDF](https://fenix.tecnico.ulisboa.pt/downloadFile/1126518382322406/Sequoia%20Capital_pitchdecktemplate.pdf)).

### 3.2 Two methods (do both, show one)
- **Top-down:** start from a published total (EU spend on X), apply a % share for the segment, then a % share we could reach. It's fast but hand-wavy. Use it only as a **cross-check**.
- **Bottom-up (headline):** `# of target units × adoption % × price per unit per year`. Each factor carries a source or a clearly labelled assumption.
  - Units can be enterprises, sites, clinicians, patients or transactions, from Eurostat, Statistics Finland or the partner itself.
  - Price can be the partner's current cost of the status quo, a competitor's public price, or the value created × 10–20% (labelled as an assumption).
- **Sanity check:** if top-down and bottom-up land within an order of magnitude of each other, the number is defensible. If they don't, find out why before showing either ([Waveup](https://waveup.com/blog/top-down-and-bottom-up-market-size-calculation)).

Definitions for the slide:
- **TAM:** everyone with the job, worldwide or EU-wide.
- **SAM:** the segment our product and channel can actually serve. Example: Nordic mid-size food logistics firms that already run a WMS with an API.
- **SOM:** what we could realistically win in 3–5 years. Start with the partner, then a beachhead country.

**Worked skeleton** (all numbers are placeholders; fill them from sources):
```
SAM units   = <N> Finnish/Nordic enterprises in NACE <code> with 50+ employees   [Eurostat sbs_sc_ovw / StatFin, year]
x adoption  = 10% in 5 yrs                                                       [ASSUMPTION; cf. EU AI adoption 20% of firms 2025]
x price     = EUR <p>/site/yr                                                    [competitor public price, or 15% of measured savings]
= SOM       = EUR <x> M/yr        (TAM cross-check: EU-27 units x price = EUR <y> M)
```
A useful anchor: Eurostat (Dec 2025) reports that **20% of EU enterprises with 10+ employees used AI in 2025**, up from 13.5% in 2024. Denmark had about 42%, **Finland 37.8%** and Sweden 35.0%. Dataset `isoc_eb_ai`, release DDN-20251211-2 ([Brussels Times](https://www.brusselstimes.com/1878918/one-fifth-of-eu-businesses-use-ai-technologies), [Implicator](https://www.implicator.ai/denmark-leads-europe-in-business-ai-use-at-42-eurostat-data-shows/); these are **secondary**, so open the Eurostat release before citing). This works as a "why now / Finland is an early-adopter beachhead" line.

### 3.3 Credible free sources for EU and Nordic numbers
| Source | Good for | Access / note |
|---|---|---|
| **Eurostat** [ec.europa.eu/eurostat/databrowser](https://ec.europa.eu/eurostat/databrowser) | Enterprises by sector and size (`sbs_sc_ovw`), ICT/AI use (`isoc_eb_ai`), health, energy, transport, population | Free; SDMX/Statistics API ([API guide](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access)). The EU business economy had about 33.1 M enterprises and 162.2 M employed in 2023 ([Eurostat SBS overview](https://ec.europa.eu/eurostat/statistics-explained/index.php/structural_business_statistics_overview); large firms about 0.2% of enterprises, [Eurostat news](https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20241205-1)) |
| **Statistics Finland – StatFin** [pxdata.stat.fi](https://pxdata.stat.fi/PXWeb/pxweb/en/StatFin/) | Finnish population, enterprises, health expenditure, wages, energy | Free, CC BY 4.0 (credit the source). PxWeb API at `https://pxdata.stat.fi/PXWeb/api/v1/en/StatFin`; export to CSV/XLSX/JSON ([stat.fi open data](https://stat.fi/en/services/statistical-data-services/open-data-and-interfaces)). Note: the px structure changed on 8 Jun 2026, so old API queries may break |
| **OECD Data Explorer** [data-explorer.oecd.org](https://data-explorer.oecd.org) | Cross-country health spending, productivity, digital and labour data | Free; SDMX API ([OECD DE](https://www.oecd.org/en/data/datasets/oecd-DE.html)) |
| **WHO Global Health Observatory** [who.int/data/gho](https://www.who.int/data/gho) | Disease burden, health-workforce indicators | Free OData API ([rgho vignette](https://search.r-project.org/CRAN/packages/rgho/vignettes/a-intro.html)) |
| **Finnish agencies** | THL (health and welfare), Kela (benefits), Traficom (transport and telecom), Fingrid (grid open data), Business Finland, Tax Administration | Free; Finnish-first, English summaries exist. Good for "in Finland, X people/year…" |
| **Nordic Statistics / SCB / DST / SSB** | Nordic comparisons; Sweden, Denmark and Norway beachhead numbers | Free; PxWeb-style |
| **Eurobarometer, EU-OSHA, ECDC, EEA, EC Digital Decade reports** | Attitudes, workplace harm, health, environment, digital adoption | Free PDFs with tables; cite the table number |
| **Company annual reports** (partner's own, Kesko, S Group, Valio, listed competitors) | Revenue, volumes, headcount, stated cost pressures. The best way to size "the partner as customer #1" | Free on investor-relations pages; cite page numbers |
| **Statista (free Basic)** | Quick snippets; trace them back to their original source | About 7% of statistics are free; free charts may be used with a link back to the Statista page ([Statista account help](https://www.statista.com/getting-started/statista-account-setup-setting-up-a-basic-account), [citation rules](https://www.statista.com/getting-started/publishing-statista-content-citation-and-integration)). Prefer citing the **underlying source** Statista names. Example: Finland's general government health expenditure was about €19.9 bn in 2022 (Statista citing Statistics Finland, [link](https://statista.com/statistics/538098/total-general-government-expenditure-on-health-in-finland); confirm in StatFin) |
| **Our World in Data, World Bank, ILO** | Global context, charts | Free, CC BY |

Avoid paid "market research report" landing pages (the "$X bn by 2032, CAGR Y%" kind). Their numbers are unverifiable and judges know it. If you must use one, label it "industry estimate" and never use it as the headline.

### 3.4 Citation hygiene
- Cite the **primary source** (Eurostat, StatFin, the annual report), not the blog or Statista page that quoted it.
- Every number gets a **year, a geography and a unit**: "€19.9 bn (FI, general government, 2022)", not "€20 bn".
- On the slide, use small-print footnotes: `Source: Eurostat isoc_eb_ai (2025)`. Put full URLs in the README and `sources.md`.
- Keep three labels distinct: **measured** (our demo or pilot), **reported** (by an official source or the partner) and **assumed** (our estimate). Never blend them without saying so.
- Round honestly: "~€40 M", not "€41.37 M". Fake precision invites the question "where's that from?".
- Partner data is confidential and the repo is public under MIT, so put **aggregates** only on slides, and only with the rep's OK.

### 3.5 How to present it without overclaiming
- One slide or half a slide at most, with the **bottom-up formula visible**: `3,200 Nordic sites × 10% × €6k = €19 M/yr SOM` (placeholder numbers). Judges trust visible arithmetic.
- Lead with the **beachhead** (the partner, then Finland), not "a €400 bn global market".
- Say "addressable by this product" rather than "our market". Don't sum TAMs from several industries.
- If the number is small, frame it as the *wedge* and name the next segment. For a hackathon, a credible €10–50 M beachhead plus a clear expansion path beats an inflated TAM.
- Prepare one Q&A line on each assumption: "Why 10% adoption?" "Eurostat shows 38% of Finnish firms already use AI; we assume a quarter of them in our niche adopt within 5 years."

---

## 4. Problem size: quantify the pain (about 45 min, Fri night to Sat morning; the most important number)

### 4.1 What counts
Judges want **one strong, sourced number** that makes the pain concrete, plus the before/after the demo measures. Junction rubrics reward a measurable outcome: FTE savings (Valio Aimo), forecast accuracy (Fortum), efficiency metrics (junction-info §2D). Winners beat a baseline with a number (DroneStalker). The "one number on a slide" rule is already in our plan (junction-info §0.2/2E).

### 4.2 Pain dimensions and formulas
| Dimension | Formula | Where the inputs come from |
|---|---|---|
| **Time lost** | incidents per period × minutes per incident × people affected | Partner rep, interviews, time-use or process studies |
| **Money lost** | time lost × loaded hourly cost; or direct losses (waste, penalties, fraud) | StatFin wage tables (salary × about 1.2–1.3 for loaded cost; label it as an assumption), the partner's annual report |
| **Error rate** | errors ÷ cases; downstream cost per error | Partner data, academic papers, regulator reports |
| **People affected** | population with the condition or role | Eurostat, StatFin, THL, WHO |
| **Delay** | wait time or lead time vs target | Public-sector KPIs (Espoo, THL waiting-time stats), partner SLAs |
| **Environmental** | kWh, kg CO2, kg waste | Fingrid, EEA, partner sustainability report |

Turn it into a **"cost of doing nothing"** line: "Finnish <role>s spend ~<n> h/week on <job> = €<x> M/yr at national scale (StatFin wages × THL headcount)." Then show **our measured delta** from the demo: "In our demo on the partner's sample: 15 min → 40 s per case (n=50 cases)."

### 4.3 Finding the one stat fast (search patterns)
- `site:ec.europa.eu/eurostat <topic> <year>`; `site:stat.fi <topic>`; `site:thl.fi <topic> English`; `site:oecd.org <topic> Finland`.
- `"<problem>" "per year" filetype:pdf site:europa.eu`. EU agency reports contain quotable tables.
- The partner's annual report: search for "cost", "efficiency", "waste", "headcount" and "risk" in the PDF.
- Google Scholar: `<problem> cost Finland OR Nordic OR Europe`, then read the abstract only and cite the paper.
- Ask the partner rep directly: "If you had to put one number on this problem, what would it be?". Quote it as "partner estimate".

### 4.4 Quality bar for "the" number
It must:
1. come from a primary or official source or the partner;
2. be ≤5 years old;
3. match our user's geography or segment, or be clearly labelled as EU/global;
4. be stated in the user's unit (minutes, euros, patients) rather than as an abstract %;
5. be one number, not three.

Run the "so what" test: "Every night shift loses ~5 hours to phantom stock errors" beats "inventory inaccuracy costs retailers billions".

---

## 5. Solution in short: one-liners (about 20 min; write it Fri night, refine Sat)

Judges score partly on whether they can explain your project to another judge later. A "one-line identity" survives that, while three features with no centre do not ([Kurbaitaev](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)). Write 5 variants, test them on 3 strangers, and keep the one they can repeat back.

**Templates**
1. **"X for Y":** "Copilot for warehouse shift leads". This only works if X is famous and the analogy really holds.
2. **Moore's positioning statement** (*Crossing the Chasm*): "**For** <target user> **who** <need>, <product> **is a** <category> **that** <key benefit>. **Unlike** <primary alternative>, **we** <key differentiator>" ([summary](https://documentdrivendx.github.io/helix/research/geoffrey-moore-positioning/); verify the wording against the book).
3. **Problem → solution → why now** (Sequoia's deck order: purpose, problem, solution, **why now**, market, competition…; [reproduced template](https://fenix.tecnico.ulisboa.pt/downloadFile/1126518382322406/Sequoia%20Capital_pitchdecktemplate.pdf)):
   - "<User> loses <number> on <job> because <root cause>."
   - "<Product> <does what> using <partner data/tech>."
   - "Possible now because <new model, API, regulation, adoption stat>."
4. **Before/after:** "Today: <status-quo number>. With <product>: <measured number>."
5. **Value proposition canvas sentence:** "Our <product> helps <user> who want to <job> by <pain reliever> and <gain creator>."
6. **Junction platform punchline** (probably ≤200 characters on the current platform, UNVERIFIED; junction-info §1). Make it a compressed form of template 2 or 4.

**Why-now ammunition for 2026 (verify each one):**
- EU enterprise AI use rose from 13.5% to 20% in one year, and Finland is at 37.8% (Eurostat 2025, above).
- New model and agent capabilities from the tech-challenge partners (Gemini and others).
- Regulatory pressure (the EU AI Act, sector regulation), if it is relevant to the brief.

**Agent-specific add-on for Raghuvanshi:** one line on where the agent fails and how the eval or reward resists gaming, for example "Fails on handwritten slips (12% of cases); flags them instead of guessing; eval set of 50 partner cases, precision 0.94." (Illustrative only; use real numbers.)

---

## 6. What juries and partner judges actually reward (evidence)

| Signal | Evidence | Implication for the research |
|---|---|---|
| **A real, specific problem** | Kanninen: "a problem worth solving, not just a feature" (Junction 2026 jury page, junction-info §2A). Söderlund: "real user problem… people want to come back to" | Specific user plus pain number plus partner quote |
| **Feasibility and adoption path** | Feasibility and adoption appear in nearly all of about 30 recent Junction partner rubrics ("path to production", "integrated straight away") (junction-info §2D). Generic guides define feasibility as whether the project can continue after the hackathon, with a concrete user pain and realistic adoption steps ([Reskilll](https://blogs.reskilll.com/what-hackathon-judges-look-for-complete-judging-criteria-breakdown-2026/), [eventflare](https://eventflare.io/journal/crafting-effective-hackathon-judging-criteria-a-step-by-step-guide)) | One line: "Pilot path: plugs into <partner system> via <API>; first site in 4 weeks" |
| **Impact as a criterion** | Devpost-hosted events commonly list "Potential Impact: the potential value and usefulness to real-world users" ([Okta hackathon](https://devforum.okta.com/t/what-are-the-judging-criteria-for-the-hackathon/15842)). Example weightings range from Impact 10% to Impact 40% ([UniTS juror kit](https://moodle2.units.it/pluginfile.php/395562/mod_resource/content/0/LAB%204%2020%20maggio%20Juror%20Guide%20Kit%20%281%29.pdf)) | The weight varies, so read the specific partner rubric on the platform Friday |
| **A measurable number** | Junction rubrics score metrics (Fortum accuracy gate, Valio Aimo FTE savings); winners beat baselines (junction-info §2D) | Before/after from our demo beats any market stat |
| **Demo over slides; technology over business plan** | MLH's judging plan: judges have about 3 min per team; "focus on learning over profit"; teams that build "product" instead of awesome technology rarely win; videos should demo, not present ([MLH Judging Plan](https://guide.mlh.com/general-information/judging-and-submissions/judging-plan)). Kurbaitaev: market context before the product costs time; slide decks didn't move scores | **Market research is supporting evidence, not the show.** About 15–20% of pitch time goes to problem and market, the rest to demo and impact |
| **Honesty about limits** | Naming a known weakness ("what breaks first at scale?") raised scores; claiming nothing breaks cost credibility ([Kurbaitaev](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)). Raghuvanshi: "why an agent fails" | Keep a "limitations and next steps" line; label assumptions |
| **Narrow scope** | Narrowly scoped, well-built projects scored higher; "judgment under a constraint is the signal" (same source) | Size the beachhead, not the world |
| **Peer legibility** | 2026 top 5 is chosen by face-to-face peer review, about 2 min per project (junction-info §1, §2D) | The one-liner and the pain number must land in 15 seconds at the table |

Bottom line: the jury rewards **specific user, sourced pain, measured improvement, credible path** far more than **big TAM**. Market sizing is a hygiene factor. A missing or inflated number hurts, but a great one rarely wins on its own.

---

## 7. Time-boxed schedule across the Junction weekend (Europe/Helsinki)

| When | Research and marketing task (Madalina, unless noted) | AI agent can do | Needs a human | Output |
|---|---|---|---|---|
| **Thu–Fri before 18:00** | Set up `03-research/sources.md`, `interviews.md` and the slide skeleton; pre-fetch past Junction challenges and winners for likely partners (Valio Aimo, Espoo, Aalto, TietoEvry, AstraZeneca, S-Pankki, Verda) | ✓ Archive digest per partner, source-site shortlist | Choose which partners to prep | Partner cheat-sheets |
| **Fri 18:00–19:30** briefs revealed | Read the 2–3 shortlisted briefs and **rubrics**; note the scored criteria and any metric | ✓ Summarise briefs into a rubric table; first-pass competitor scan per brief (§1 prompt) | Judge fit and feasibility for our team | Rubric matrix |
| **Fri 19:30–21:00** | **Talk to partner reps** (the 5-question script); ask for the status quo, the pain number, the data and who judges. Agent runs the competitor scan in parallel | ✓ Scan, classify, draft the table | Every conversation; verify the top 5 competitors exist | Interview notes; draft alternatives table |
| **Fri ~21:00** decision | Feed in: user card, pain hypothesis, "is this already done?" | — | Team decision (post a `board` decision) | Challenge choice |
| **Fri 21:00–23:59** | Write the proto-persona, 3 job stories and the one-liner v1; desk search for the **one pain stat** (§4.3); fill the project name and punchline for the **preliminary submission by 23:59** | ✓ Draft job stories, one-liner variants and stat candidates with URLs | Pick the stat; open the source and check the number, year and unit | User card, one-liner v1, prelim submission |
| **Fri night / Sat 08:00–10:00** | Sleep at least 4 h. In the morning: second round of partner and mentor talks with a mock or screenshot; Discord call for domain people; optional 3–5-question form | ✓ Draft survey and Discord post; tally responses | Conversations; commitments ("will you visit our table?") | Validated or adjusted user; quotes |
| **Sat 10:00–12:00** | **Market sizing** bottom-up plus a top-down cross-check (§3); pull Eurostat or StatFin tables | ✓ Pull tables via API or CSV, compute the formula, produce a sensitivity range | Choose assumptions; sanity-check orders of magnitude; partner OK on aggregates | Market half-slide plus `sources.md` lines |
| **Sat 12:00–15:00** | Comparison table and 2x2 final; refresh the competitor scan (anything new on Product Hunt or GitHub?) | ✓ Format the table; refresh the scan | Choose 2x2 axes; check each "✓" is demonstrable | Competition slide or backup |
| **Sat 15:00–20:00** | Start the deck and video storyboard (per plan): problem (user plus pain number) → solution one-liner → demo → measured impact → market/path → team. Agree with the builders **what metric the demo will measure** and how (baseline vs ours) | ✓ Slide text drafts, speaker-note drafts, citation footnotes | Narrative; what to cut | Deck v1 |
| **Sat evening** (builders integrate) | Get the **measured number** from the build (time per case, accuracy vs baseline, n). Write the README "Problem / Users / Impact / Sources" sections | ✓ README drafting, consistency check slide ↔ sources | Verify the measurement method is honest | README sections |
| **Sun 00:00–06:00** | Final one-liner test on 3 strangers; record the video; rehearse the 2-min peer-review pitch and the 15-s opener | ✓ Script tightening to word count | Recording, rehearsal | Video, final deck |
| **Sun 06:00 freeze → 10:00 submit** | Final fact-check pass: every slide number has a matching `sources.md` line; labels reading measured, reported or assumed are present; no partner raw data in the repo; submit well before 10:00 | ✓ Automated cross-check of numbers between deck, README and sources | Final sign-off and submission | Submitted project |
| **Sun after 10:00** | Peer review: user card plus pain number in 15 s, demo, measured delta, one honest limitation | — | All human | Top-5 shot |

Total desk research is about 6 h, plus 2–3 h of conversations, spread across Fri night and Sat morning. After Saturday 15:00, research time drops to fact-checking only.

### 7.1 AI agent vs human split (summary)
**Delegate to an AI research agent**, with an instruction to return URLs and mark anything not opened as UNVERIFIED:
- broad competitor and prior-art scans (Devpost, GitHub, Product Hunt, YC, app stores) and classification;
- digesting past Junction challenges and winners for a partner;
- pulling Eurostat, StatFin and OECD tables via API and doing the arithmetic, including sensitivity ranges (low, mid, high);
- drafting job stories, one-liner variants, survey questions, the Discord post, README sections and slide copy;
- consistency checks between deck, README and sources.

**Keep human:**
- every conversation with partners, mentors and users (the agent can't be in the room, and the quotes are the evidence);
- choosing the user, the job, the beachhead and the 2x2 axes;
- opening and confirming every number that goes on a slide (agents misread years, units and geographies, and invent competitors and stats);
- deciding what is measured vs assumed, and the measurement method;
- partner-data confidentiality calls;
- the pitch delivery itself.

**Known agent failure modes to watch for:**
- invented companies or URLs;
- stale "market report" CAGR numbers;
- a US number presented as an EU one;
- mixing up the year of the data with the year of publication;
- treating Statista as the primary source;
- accepting the agent's "verified" without opening the link.

---

## 8. One-page checklist (print this)
- [ ] Rubric criteria copied; the metric the partner cares about identified
- [ ] At least 2 partner or mentor conversations logged, with 1 quotable line
- [ ] User card: role, context, job story, status quo, pain number, quote
- [ ] Alternatives: direct, indirect, status quo and the partner's internal tool; 2x2 or table; "Unlike X, we Y"
- [ ] ONE pain stat: primary source, year, geography, unit
- [ ] Measured before/after from our demo (n, method)
- [ ] Bottom-up SOM with visible arithmetic; top-down cross-check within about 10x; assumptions labelled
- [ ] One-liner passes the "repeat it back" test with 3 strangers; punchline fits the platform limit
- [ ] Why now: one verified stat
- [ ] Limitations and failure-case line (agent projects: why it fails, and the eval)
- [ ] `sources.md` complete; no partner raw data or secrets in the public repo
