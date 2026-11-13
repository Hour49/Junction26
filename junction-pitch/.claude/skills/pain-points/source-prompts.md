# /pain-points subagent prompts

Launch all five in ONE message (five Agent calls in the same reply), `subagent_type: pain-points-searcher`.
Six source families on five searchers (cap: 5 agents per run): searcher 3 gets blocks 3 AND 4 and writes one
file, `reviews.md`. The others get one block each.
If that agent type is not available, use `general-purpose` with `model: haiku` and paste the rules from
`.claude/agents/pain-points-searcher.md` at the top of each prompt.

Each prompt = the **common block** (fill the `<...>`) + that searcher's **family block(s)**.

## Tested sources (2026-11-10)

These open without a login. `PW` = open in the agent's Playwright browser. `H` = covered by the helper
`python3 .claude/skills/pain-points/fetch_public.py <source> "<query>"` (run from the project root; it runs
without a permission prompt). `WF` = open with WebFetch. A 403 to the helper may still work in WebFetch.

| Source | URL pattern | How | Notes |
|---|---|---|---|
| Hacker News | `https://hn.algolia.com/api/v1/search?query=<q>&tags=comment` (or `story`) | H `hn` | Link: `https://news.ycombinator.com/item?id=<objectID>` |
| Stack Exchange | `https://api.stackexchange.com/2.3/search/advanced?q=<q>&site=<site>` | H `se --site <site>` | Needs a real site: money, cooking, softwareengineering, workplace, ux, travel, … (`site=stackexchange` is invalid) |
| GitHub issues | `https://api.github.com/search/issues?q=<q>` | H `gh` | Low rate limit without a key: few calls, pause between them |
| Apple App Store search | `https://itunes.apple.com/search?term=<app>&country=fi&entity=software` | H `appsearch --country fi` | Gives the app id. Never guess an id |
| Apple App Store reviews | `https://itunes.apple.com/<country>/rss/customerreviews/page=<1-10>/id=<appId>/sortBy=mostRecent/json` | H `appreviews <id> --country fi --maxstars 3 --page 1` | Countries fi, se, gb, us. Full review text. Cite `https://apps.apple.com/<country>/app/id<appId>` + the date |
| Google Play | `https://play.google.com/store/apps/details?id=<pkg>&hl=en` | WF | Large page; reviews only partly render. Best-effort |
| Trustpilot | `https://www.trustpilot.com/review/<domain>?stars=1&stars=2` | WF | 403 to the helper; worked in WebFetch |
| G2 / Capterra | product review pages | WF | Often blocked: log it and move on |
| OpenAlex | `https://api.openalex.org/works?search=<q>` | H `openalex` | Papers + abstracts |
| Crossref | `https://api.crossref.org/works?query=<q>` | H `crossref` | |
| PubMed | E-utilities `esearch.fcgi` + `esummary.fcgi` | H `pubmed` | Health track |
| openFDA | `https://api.fda.gov/drug/event.json?search=<expr>&limit=5` | H `openfda` | Counts of adverse-event reports; health track |
| CFPB complaints | `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?search_term=<q>&size=5` | WF | 403 to the helper, **works in WebFetch** (JSON). FinTech, US only |
| Eurostat | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>?geo=FI` | WF | Find the dataset code by WebSearch first |
| Wikipedia | `https://<lang>.wikipedia.org/w/api.php?action=query&list=search&srsearch=<q>&format=json` | H `wiki --lang fi` | Background only, never a statistic source by itself |
| Suomi24 (Finnish forum) | `https://keskustelu.suomi24.fi/haku?keyword=<q>&jarjestys=osuvimmat` | H `suomi24` | Put exact phrases in "double quotes", else results are noise |
| YouTube | `https://www.youtube.com/results?search_query=<q>` | WF | Video titles only (leads, not quotes) |
| Any public page | — | H `page "<url>" --grep "<word>"` | Plain text around a word: use it to copy quotes longer than ~125 characters |
| GDELT news | `https://api.gdeltproject.org/api/v2/doc/doc?query=<q>&mode=artlist&format=json` | WF | Rate-limited (429). At most one call, optional |

**Login-walled sources (private):** Reddit, X/Twitter, LinkedIn, Quora, Facebook and paid report sites. Open
them in Playwright (`PW`); the saved logins in `.playwright/auth.json` usually get through. Still a login wall:
log `needs login: <site>`, never type a password. **Research papers:** arxiv MCP (`search_papers`,
`read_paper`). **Blocked by WebFetch (403):** retry the page in Playwright before logging it blocked.

**WebFetch limit:** it copies at most about 125 characters verbatim. For a longer exact quote use the helper
(`page --grep`, or the JSON sources, which return the full text).

## Common block (same for all five)

```text
Problem: <one sentence from search-plan.md>
Our idea: <one sentence, or "none yet">
User roles: <list>
Challenge track: <e.g. retail, health, fintech, mobility, or "unknown">
Today: <YYYY-MM-DD>. Based on core.md: <line from search-plan.md>
Search plan (phrasings, Finnish phrasings, synonyms, competitor names, "not this"):
<paste the lists from 03-research/pain-points/<slug>/search-plan.md>

Your source family: <name>. Search only there.
Write your results to: /home/madi/junction-pitch/03-research/pain-points/<slug>/<file>.md
Use the "Source file" template in /home/madi/junction-pitch/.claude/skills/pain-points/templates.md.
Sources: the table "Tested sources" in
/home/madi/junction-pitch/.claude/skills/pain-points/source-prompts.md. Helper (run from
/home/madi/junction-pitch): python3 .claude/skills/pain-points/fetch_public.py -h
Use WebSearch only to find links. Open web pages in Playwright; use the helper for its JSON APIs and the
arxiv MCP for papers. Public AND private sources (mark each). Login wall in Playwright: log "needs login: <site>",
never type a password. Anything else still blocked: log "blocked: <url>".
Rules: no link = no quote; exact words only, copied from the opened page or API response, never from search
snippets; ≤40 words; role only, no usernames; date on every quote; mark match level (exact/close/adjacent)
and emotion (1–3); non-English quotes stay original plus "(our translation)"; mirrors and SEO copies are not
sources. Never invent.
Final message: ALL findings for the orchestrator (format in your agent file), plus blocked and needs-login lists.
```

## 1. Public research and surveys → `research.md`

```text
Source family: research (public and private) that QUANTIFIES the problem. Main output: statistics, not quotes.
- Papers: helper `openalex`, `crossref` (and `pubmed` for health). Read the abstract; open the DOI page with
  Playwright for the number. Search arxiv with the arxiv MCP (`search_papers`, then `read_paper`) for
  preprints; mark them "preprint". A paper's number is only "reported" if you saw it on the page or in the abstract.
- Statistics: Eurostat (WebSearch "eurostat <topic> dataset", then the API URL in WebFetch), Statistics
  Finland (site:stat.fi <topic>), OECD (site:oecd.org <topic> Finland).
- Consumer organisations and regulators: Which? (which.co.uk), Kuluttajaliitto (kuluttajaliitto.fi), KKV
  (kkv.fi), BEUC, national regulators' reports. Surveys with sample size and year.
- Follow 01-playbooks/market-research.md §4.3 search patterns ("<problem>" "per year" filetype:pdf site:europa.eu).
- For each number: claim, number, unit, year, geography, source title, URL, accessed, primary/secondary,
  confidence. Prefer primary, ≤5 years old, our user and geography (playbook §4.4).
- End with "Best candidate for THE number": which one, and why.
- Never compute a new number and present it as reported. If you combine numbers, show the arithmetic and
  label the result assumed.
```

## 2. News → `news.md`

```text
Source family: news articles. Real people quoted in articles count; the article is the source.
- WebSearch to find articles: Finnish first (yle.fi, hs.fi, is.fi, iltalehti.fi, mtvuutiset.fi,
  kauppalehti.fi) with the Finnish phrasings, then Reuters, BBC, trade press for the industry.
- Open each article with WebFetch. Quote only words inside quotation marks in the article, said by a named
  role (e.g. "a Helsinki customer told Yle"). Platform cell: "<outlet> (quoted person)". Role only, no names.
- Numbers in articles: record them as reported, with the original source the article cites if given;
  secondary unless it is the outlet's own survey.
- Paywalled article (HS, Kauppalehti): log "blocked: <url> (paywall)" and move on; do not quote the teaser.
- GDELT (optional): at most ONE call to the URL in the table, for a coverage count or extra links. On 429,
  log it and do not retry.
```

## 3. App store reviews → `reviews.md` (same searcher also does block 4)

```text
Source family: app store reviews of competing, partner or status-quo apps.
- List 3–6 REAL apps (from the search plan, or helper `appsearch "<name or problem word>" --country fi`).
  Use the trackId the search returns; never guess an id.
- Helper `appreviews <id> --country fi --maxstars 3 --page 1` (then pages 2–3; also se, gb, us if relevant).
  1–3-star reviews are gold. Read them all; keep the ones about our problem.
- The review text in the feed is the review itself: quote it exactly. Link: https://apps.apple.com/<country>/app/id<id>
  (individual reviews have no public URL; give the date, stars and app). Platform cell: "App Store FI, <app>, 2★".
- Google Play (best-effort): WebFetch https://play.google.com/store/apps/details?id=<pkg>&hl=en and quote only
  review text you can see verbatim.
- Note how many low-star reviews mention the problem out of those read (e.g. "6 of 140"), labelled
  measured-by-us on a small sample, not a statistic.
```

## 4. Review sites → `reviews.md` (same searcher as block 3)

```text
Source family: review sites, best-effort (Trustpilot, G2, Capterra).
- Trustpilot via WebFetch: https://www.trustpilot.com/review/<domain>?stars=1&stars=2 (also fi.trustpilot.com).
- G2 / Capterra via WebFetch for B2B tools (find the product page with WebSearch site:g2.com "<product>").
- Record which sites worked and which were blocked, in "Searched but empty or blocked".
- Record star rating and product with each quote (Platform cell, e.g. "Trustpilot, <brand>, 1★").
```

## 5. Open forums with public APIs → `forums.md`

```text
Source family: forums. Open ones via the helper; Reddit, X, LinkedIn and Quora via Playwright
(logged in through .playwright/auth.json; search inside the site, e.g. reddit.com/search?q=<words>).
- Hacker News: helper `hn "<words>"` (comments) and `hn "<words>" --tags story`. Short keyword queries work
  best (3–4 words). Comment text in the output is verbatim.
- Stack Exchange: helper `se "<words>" --site <site>`; pick 2–3 relevant sites (money, cooking, workplace,
  ux, travel, parenting, softwareengineering, …).
- GitHub issues: helper `gh "<words>"` only for developer or tool problems. Few calls (rate limit).
- Suomi24: helper `suomi24 '"<exact Finnish phrase>"'` (keep the double quotes inside), 3–5 Finnish phrasings.
  The listing shows only the start of each thread: open promising threads with
  `page "<thread url>" --grep "<word>"` and copy the exact words from there.
- No output from the helper = no hits for that query; log it as empty.
```

## 6. Domain complaint data → `complaints.md`

```text
Source family: complaint and incident data for the challenge track. Turn it into counts or trends, labelled
reported (or measured-by-us if you counted records yourself, with the query).
- Health: openFDA (helper `openfda '<field>:"<value>"'`; gives a total count of reports), PubMed for
  complaint studies.
- FinTech: CFPB complaints API via WebFetch (URL in the table; US only), Finnish FIN-FSA (finanssivalvonta.fi)
  and FINE (fine.fi) complaint statistics.
- Consumer goods and services, any track: KKV and Kuluttajariitalautakunta (kuluttajariita.fi) statistics,
  EU Consumer Conditions Scoreboard and Consumer Markets Scoreboard (commission.europa.eu), BEUC, Which?.
- Partner or industry reports: annual reports, industry associations (label secondary).
- Each count: what was counted, the exact query or table, period, geography, URL, accessed. Show a trend
  (e.g. 2021 vs 2025) only if both numbers come from the same source.
- Narratives in complaint data (e.g. CFPB "complaint_what_happened") may be quoted exactly as a quote, role
  "US consumer".
```
