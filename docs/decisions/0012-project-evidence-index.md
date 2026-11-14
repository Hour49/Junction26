# 0012: A project's files that are not floor plans are searchable through a local hybrid index (BM25 + a multilingual embedder), offered to the chat agent as two tools

- Status: proposed
- Date: 2026-11-14 16:52 (Europe/Helsinki)
- Decided by: agent rag (worker, in charge of the design), for Bogdan ("Are we lacking a free form LLM chat agent?
  WIth tool calls s othat will work with the hybrid rag and other tool calls? [...] Tudor will work on the agent
  chat and I was thinking for you to work on the hybrid rag. In the rag there should be the descriptions of the
  other sources of evidence not floor plans", 2026-11-14); to be approved by Bogdan's orchestrator and reviewed by
  Tudor's fleet
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

**Passages.** Per file: one `summary` (kind in words, subject, the short text); the long description split at
sentence ends into passages of at most 500 characters; the printed text packed by lines the same way. Ids are
`<file id>-<part>[-<n>]`: `f7-summary`, `f7-detail-2`, `f7-visible_text-1`. The judge's `why` is returned with a
file but not searched.

**Retrieval.** Two rankings of files, each by a file's best passage, fused by reciprocal rank fusion with k=5:

- BM25: SQLite FTS5 (`unicode61 remove_diacritics 2`), the query's words joined by OR.
- Dense: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0), its 8-bit ONNX file (118 MB)
  on CPU through onnxruntime and `tokenizers`; mean pooling, unit length, 384 numbers; a passage is embedded as
  `<subject>. <passage>`; vectors are float32 blobs in the same SQLite file, compared by brute force. The model
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
{"query": "south facade photo", "method": "hybrid: BM25 + multilingual MiniLM, reciprocal rank fusion",
 "indexed_files": 14, "unrelated_left_out": 3, "note": null,
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
