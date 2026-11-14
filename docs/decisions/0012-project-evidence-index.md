# 0012: A project's files that are not floor plans are searchable through a local hybrid index (BM25 + a multilingual embedder), offered to the chat agent as two tools

- Status: accepted by Bogdan's orchestrator (2026-11-14: "contract, eval (hybrid k=5 92/100), ADR and manifest
  accepted"); the tool shapes confirmed by Tudor's agent orchestrator (board #220, c6879237435); built in PR #235.
  Amended 2026-11-14 (Amendment 1 below: what is indexed), accepted by Bogdan's orchestrator ("Amended 7.2 rule
  accepted", "Carbon describer per your rule"); built in PR #267
- Date: 2026-11-14 16:52 (Europe/Helsinki)
- Decided by: agent rag (worker, in charge of the design), for Bogdan ("Are we lacking a free form LLM chat agent?
  WIth tool calls s othat will work with the hybrid rag and other tool calls? [...] Tudor will work on the agent
  chat and I was thinking for you to work on the hybrid rag. In the rag there should be the descriptions of the
  other sources of evidence not floor plans", 2026-11-14)
- Board thread: #220 (the tool format)

## Context

- File triage (decision 0010) sets aside every image that is not a floor plan and describes it: a subject line, 1-3
  sentences, a long description (up to 4,000 characters) and every word printed on it. Nothing reads those texts
  today. `POST /api/projects/{id}/ask` answers from floor-plan readings only.
- The free-form chat agent (Tudor's fleet) calls tools. The law knowledge base (decision 0011) gives it
  `search_law` and `get_clause`; it needs the same for "what else is in this project": photos, elevations,
  sections, site plans, maps, text pages.
- The texts are in English, the printed words in the file's own language, and people here ask in Finnish too.
- Local-first: no paid call when a file is indexed or a query runs.

## Decision

**What is in the index.** Every file of a project that has a triage description and was not read as a floor plan.
Floor plans stay out: their facts come from the pipeline's answers. The index is derived from the project's status
and can always be rebuilt from it; a project ingested before this decision is indexed when it is first opened.
With `EVIDENCE_SCOPE=all_non_plan` more files are indexed: see Amendment 1.

**Passages.** Per file: one `summary` (kind in words, subject, the short text); the long description split at
sentence ends into passages of at most 500 characters; the printed text packed by lines the same way. Ids are
`<file id>-<part>[-<n>]`: `f7-summary`, `f7-detail-2`, `f7-visible_text-1`. The judge's `why` is returned with a
file but not searched.

**Retrieval.** Two rankings of files, each by a file's best passage, fused by reciprocal rank fusion with k=5:

- BM25: SQLite FTS5 (`unicode61 remove_diacritics 2`), the query's words joined by OR.
- Dense: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0), its 8-bit ONNX file (118 MB)
  on CPU through onnxruntime and `tokenizers`; mean pooling, unit length, 384 numbers; a passage is embedded as
  `<subject>. <passage>`, one text per model run (the 8-bit model's vector for a text shifts a little with the
  other texts in a batch); vectors are float32 blobs in the same SQLite file, compared by brute force. The model
  and tokenizer are pinned by revision and sha256 in `data/models/rag/manifest.json`.

Files a person or the judge called unrelated are left out before ranking unless the caller asks for them. With no
model file on the machine the index answers with BM25 alone and says so (the no-models mode).

**Tools** (`backend/app/adapters/evidence_tools.py`, OpenAI function-calling JSON, as the law tools):
`EVIDENCE_TOOLS` holds `search_evidence(query, k=5, include_unrelated=false)` and `get_evidence(id)`;
`run_evidence_tool(index, name, arguments) -> str` (arguments as JSON text or a dict) never raises and answers a
bad call with `{"error": "<sentence>"}`; `evidence_prompt(index) -> str` is a paragraph for the system prompt. The
index is one project's: the agent loop binds it, the model passes no project id. A search returns at most one hit
per file:

```json
{"query": "south facade photo",
 "method": "hybrid: BM25 + paraphrase-multilingual-MiniLM-L12-v2, reciprocal rank fusion", "indexed_files": 14, "unrelated_left_out": 3, "note": null,
 "hits": [{"id": "f7-detail-2", "file_id": "f7", "file": "photos/IMG_0412.jpg", "page": 1, "part": "detail",
           "kind": "photograph", "subject": "south facade of a two-storey brick house",
           "snippet": "The south facade is red brick with three windows on the upper floor ...",
           "language": "fi", "verdict": "related", "credit": null, "score": 0.31,
           "why": {"terms": ["south", "facade"], "bm25_rank": 1, "dense_rank": 2}}]}
```

`get_evidence` returns the whole passage and the file's description, register and relevance as
`GET /api/projects/{id}` gives them. A hit is the closest file, not proof: the tool description tells the agent to
read the snippet and to call `get_evidence` before it states a fact.

**REST** (additive, the same JSON): `GET /api/projects/{project_id}/evidence/search?q=&k=&include_unrelated=` and
`GET /api/projects/{project_id}/evidence/{evidence_id}`; errors in the API's `{"detail", "code"}` shape.

Owners: agent rag the design and the eval, agent eu-big the backend, Tudor's fleet the agent loop.

## Alternatives considered

Measured on 214 described non-plan files of the Stoa preview set searched as one project, with 100 questions in
three sets written before each run (recall@5 at file level; method and limits in the PR):

| | 50 questions (30 English, 20 Finnish) | 20 by a printed identifier | 30 fresh | All 100 |
| --- | --- | --- | --- | --- |
| BM25 alone | 37 | 20 | 24 | 81 |
| Embedder alone | 47 | 6 | 18 | 71 |
| Hybrid, k=60 | 46 | 15 | 23 | 84 |
| Hybrid, k=5 (this decision) | 46 | 20 | 26 | 92 |

- BM25 alone: finds a sheet by its number, date or signature every time, but only 7 of 20 Finnish questions, since
  the descriptions are English.
- The embedder alone: carries Finnish questions to English descriptions, but finds only 6 of 20 files by a printed
  identifier ("HAER NH-50, sheet 7 of 9" came 166th).
- The usual fusion constant k=60: a file one ranking puts first and the other does not rank ends up below files
  both rank around tenth. k=5 was picked on the first two sets and confirmed on the third (26 against 23).
- `intfloat/multilingual-e5-small` as the embedder: 43 of 50 against MiniLM's 46 on the first set.
- `bge-m3`: about five times the size; not tried, the small models passed.
- A vector database or an approximate index: a project has tens to hundreds of files, a few thousand passages at
  most; brute force over them takes about 3 ms.
- Image embeddings: the descriptions already exist and carry the printed text; a second model for little gain.
- A paid embedding API: breaks local-first.

## Consequences

- The agent can answer "is there a photo of the south facade?" or "which sheet is CT-185-M?" from the project's
  own files, with the file to show.
- New backend dependency `tokenizers`, and a 118 MB model file to put on the deploy machine. Indexing costs about
  10 ms per passage on a desktop CPU (about 50 ms per file); it has to be measured on the ARM deploy box.
- Descriptions exist only when triage and the describer run. With triage off the index is empty and says so.
- Known weak spot: a natural Finnish question over English descriptions is found 22 times of 30, against 63 of 63
  for English. The tool description therefore asks the agent to search in English and keep names and numbers as
  printed.
- The right file is among the first five more often than it is first (recall@1 0.55 to 0.80 by set). Fine for an
  agent that reads five snippets; a search box showing one result would need more work.
- Revisit when: the describer starts writing in the project's language; a project grows past a few thousand files;
  real users' questions show a kind of question the three sets lack.

## Amendment 1 (2026-11-14): everything that is not a floor plan is indexed

- Date: 2026-11-14 17:51, rule amended 17:58 (Europe/Helsinki)
- Decided by: agent rag, for Bogdan ("everything, as a normal hybrid rag search on the description of the non
  floor plans", 2026-11-14 17:45, when asked what the demo should be able to find)

### Context

- The decision above indexes only what file triage sets aside and describes, and triage looks at images and scans.
  In a real drawing set most of what is not a floor plan is a drawn (vector) PDF: elevations, sections, the site
  plan, the roof plan, schedules. Those never reached the describer. Text documents were kept as "text only" and
  not searched. In the three demo projects the index held one file of 42.
- Reading a file as a plan and describing it for the index were one decision. Tying them together means that
  widening the index would set more files aside, and a plan set aside is never read.

### Decision

**A setting.** `EVIDENCE_SCOPE=set_aside|all_non_plan`. `set_aside` is the default and is the decision above,
unchanged. With `all_non_plan`, every file and every PDF page that is not a floor plan becomes a source.

**Describing for the index is separate from setting aside.** The scope never changes how a file is routed. What is
read as a plan with the scope off is read as a plan with it on, with the same state, route and takeoff. A file can
therefore be both read and described. The record of the new step is `FileStatus.evidence` (is it indexed, how,
its kind, one sentence why, the kind reply, the description), next to `triage`, which keeps its meaning.

**What becomes a source.**

| File | How | From what | Paid call |
| --- | --- | --- | --- |
| An image triage set aside and described | `described` | its triage description, as before | as before |
| Any other picture: a PNG or JPEG, a scanned PDF page, a drawn PDF page (a multi-page PDF's later drawn pages are files of their own) | `described`, when the kind rule below says so | the describer's form, from the page rendered to an image | one kind call, then one description |
| A text document (a text PDF, a plain text file), and the text pages inside another PDF | `text` | its own text, cut per page into passages of at most 500 characters; contact data cut as in descriptions; at most 200,000 characters per file | none |
| A file nothing reads: DWG, office document, IFC model, archive, encrypted PDF, unknown type | `listed` | its name, type and size; the passage says its content is not read | none |

**The kind rule for a picture.** One call to the sheet-kind reader (`sheet-kind-2` on gemini-4-carbon, the reader
of the `SHEET_KIND` step, with its cache; a file is asked once whichever setting asks). The picture is a source
when the reply's sheet kind is neither "architectural floor plan" nor "several views", or when it says no floor
plan is on the sheet and the kind is not "architectural floor plan". No confidence cut. A failed call, a spent
budget or a page that cannot be rendered is not a source, and the file's record says why.

**The describer.** For `all_non_plan` the demo sets `TRIAGE_DESCRIBER=carbon`: the same prompt (`describe-6`) on
gemini-4-carbon. `gemini` (gemini-3.5-flash) stays the default value.

**Passages and tools.** A described source is cut exactly as before, so the measured retrieval is untouched. A
text source has a `summary` (kind, file name in words, its first 300 characters) and `text-1..n` passages, each
with the page it comes from. A listed source has one `summary`. The tools and REST routes gain, and lose nothing:
a field `how` (`described`, `text`, `listed`), the part `text`, and new kinds (the sheet kinds, `text_document`,
`text_file`, and the listed file types). The system-prompt paragraph tells the agent that a text document is
quoted from its own text and that a listed file was not read.

**Not indexed.** A floor plan sheet. A several-views sheet with a floor plan on it. DXF and SVG files: nothing
renders them for a kind call, and most are copies of a sheet that has one. The inside of office documents, DWG
files and IFC models.

### Alternatives considered

Kind rules, counted on the cached replies of the sheet-kind gate run: 675 hand-checked sheets that are not the
demo's files (416 with no floor plan, 227 with one somewhere on the sheet, 32 either way). The set over-samples
hard sheets.

| Rule | Sheets with no floor plan that become sources (of 416) | Sheets with a floor plan that are also described (of 227) |
| --- | --- | --- |
| No floor plan on the sheet, and the kind is not floor plan | 409 | 17 |
| **That, or a kind that is neither floor plan nor several views (this decision)** | **410** | **31** |
| The kind is not floor plan, nothing else | 412 | 74 |

- The first rule was the one first written. It keeps out a site plan sheet that also draws the house's floor
  inside the lot, and that is the sheet that answers "where does the house sit on its lot". The rule was changed
  after a pilot on the demo's house set showed this on one sheet; it was then chosen on the 675 other sheets, and
  before any ingest ran with the scope on.
- The third rule brings in the several-views sheets with a floor plan: 43 more sheets of 227 would be described
  as something they are only partly.
- A confidence cut, as the set-aside step has: there a mistake loses a plan; here a plan called "no plan" is still
  read and only also described, while a sheet left out cannot be found. So no cut.
- Using `triage` for drawn PDFs: triage sets aside what it calls not a plan. The sheet-kind step did not pass its
  gate for that (7 of 227 plans set aside), so the index must not depend on it.
- One call that classifies and describes: it would change the measured describer prompt, and floor plans would
  pay for a description they do not need.
- The describer, 5 house sheets given as PDFs, same prompt:

  | | gemini-3.5-flash | gemini-4-carbon |
  | --- | --- | --- |
  | Valid form | 5 of 5 | 5 of 5 |
  | A private home's house number and postal code left out | 4 of 5 | 5 of 5 |
  | Sheet number and title read | 5 of 5 | 5 of 5 |
  | USD per sheet | 0.0095 | 0.030 (at 4 / 20 USD per million tokens, the price from December 2026; half until then) |
  | Seconds per sheet | 4 to 7 | 32 to 42 |

  The rule was fixed before the run: gemini-3.5-flash stays unless Carbon is at least as good on every sheet and
  costs at most 0.05 USD. Five sheets of one project show cost and breakage, not quality in general.
- A relevance verdict for the new sources: the judge works on triage records. Not built; every new source is
  searched by default.
- File names in the searched text of described sources: it would change the measured passages. Used only for
  text and listed sources, which have nothing else.
- Reading DXF text, office documents or IFC metadata: no reader for them is in this path yet.

### Consequences

- The chat can find a project's elevations, sections, site plan, roof plan and schedules when they are drawn
  PDFs, quote a specification by page, and say that a DWG exists without claiming to have read it.
- Cost per picture: 0.012 USD for the kind call, plus 0.030 USD for the description when it is not a floor plan;
  text and listed files cost nothing. A ten-sheet house set is about 0.36 USD, once per content (both replies are
  cached by the file's hash). All of it is charged to the Gemini spend guard.
- Time: a kind call takes 6 to 9 seconds and a Carbon description 32 to 42. One kind call in ten timed out in the
  pilot and answered when asked again. A cold ingest of a drawing set takes minutes unless the calls run side by
  side; with warm caches it takes seconds.
- A few sheets that hold a floor plan are also described (31 of 227 on the hard set): site plans with a floor in
  them, shop directory maps, ceiling and framing plans. Their descriptions may name rooms. The agent is told that
  floor plan facts come from the takeoff, not from a description.
- An elevation uploaded as a drawn PDF is still also read as a plan, as before. That is the `SHEET_KIND` step's
  question, not this one's.
- Without a describer or a key, pictures are not described and say so; text and listed sources are still indexed.
- Checked through the real ingest by a check fixed in advance: the 15 demo questions over three
  projects (at least 14 found in the first 5), no floor plan file among the sources, no difference in any file's
  state, route or takeoff against the scope off, the 100 questions of the first decision still 92, and at most
  0.05 USD per file on average. Result (2026-11-14, PR head d8a4ec5, 0.40 USD): 13 of 15 found in the first 5
  (the Finnish site-plan question at rank 6; the sample's drawn site picture is judged unrelated, so a default
  search leaves it out); one floor plan among the sources (the demo zip's photos/056.jpg, a photo of a hotel
  evacuation map that the kind call names "another kind of drawing" with no floor plan on the sheet, 0.65); no
  file's state, kind, route, group, source or takeoff differs, but every drawing id does, because the scope is
  part of the ingest cache key; still 92 of 100; 0.009 USD per file on average, at most 0.053. Lines 1 and 2
  fail.
- Revisit when: a render exists for DXF and DWG; a project's elevations sit on the same sheet as its plan; the
  describer's price or speed changes.
