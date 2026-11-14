# 0014: The AI reads building law through search over a clause-level knowledge base, never the whole corpus

- Status: accepted (law-kb orchestrator, 2026-11-14)
- Date: 2026-11-14 16:15 (Europe/Helsinki)
- Decided by: agent kb-tool, for the law-kb orchestrator (Tudor's goal: "what is the best way to give the ai access
  to these laws without injecting all of them into context?")
- Board thread: local board `.agents/law-kb/BOARD.md`; the orchestrator relays it to the team board

## Context

The assistant answers questions about a drawing and should say which Finnish or Swiss (federal + Zürich) building
rule applies, quoting it. The building law a designer needs is a few hundred laws and decrees, a few thousand
subsections, in Finnish, Swedish or German. Most questions need one to five of them. The rule packs of 0009 hold a
handful of checkable limits, not the law. Researchers (fi-law, ch-law) write the clauses; this record fixes the
format they write and how the AI reaches it.

## Decision

**Data** (`backend/app/laws/<pack>/<law id>.json`, one file per law, `LAWS_DIR`; model `app/core/laws/model.py`;
loaded and validated at start by `app/adapters/law_index.py`, like 0009's packs):

```json
{
  "id": "fi-1008-2017", "pack": "fi", "jurisdiction": "FI", "number": "1008/2017",
  "title": "Ympäristöministeriön asetus asuin-, majoitus- ja työtiloista",
  "title_en": "Ministry of the Environment Decree on residential, accommodation and work spaces",
  "url": "https://www.finlex.fi/fi/lainsaadanto/2017/1008", "language": "fi",
  "in_force": "2018-01-01", "checked": "2026-11-14", "status_note": "In force.",
  "clauses": [{
    "id": "fi-1008-2017-4-2", "ref": "4 § 2 mom.",
    "heading": "Huonekorkeus ja huoneala", "heading_en": "Room height and room area",
    "text": "Asuin-, majoitus- ja työtilan huonealan on kuitenkin aina oltava vähintään 7 neliömetriä.",
    "text_en": "The room area of a residential, accommodation or work space must ... at least 7 square metres.",
    "summary_en": "Every habitable room has a floor area of at least 7 m2.",
    "keywords": ["room area", "minimum area", "7 m2", "bedroom", "huoneala"],
    "topics": ["rooms"],
    "limits": [{"what": "habitable room area", "comparison": ">=", "value": 7, "unit": "m2"}],
    "drawing_checkable": true
  }]
}
```

The loader refuses (the app does not start, the error names the file) a law whose `id` is not its file name or
whose `pack` is not its folder; a pack other than `fi`, `ch-zh`; a jurisdiction that does not fit the pack (`fi`:
`FI`; `ch-zh`: `CH` or `CH-ZH`); a `url` that is not https; a language outside `fi sv de fr it en`; dates not
`YYYY-MM-DD`; a law with no clause; a clause id that does not start with `<law id>-` or repeats anywhere; an empty
`text` or `summary_en`; `text_en` null on a law not in English; fewer than 3 or more than 12 keywords; no topic or
one outside the closed list (`rooms accessibility fire escape-routes stairs-railings doors-windows ventilation energy
sound moisture structure daylight parking outdoor distances-heights permits-procedure general`); a limit whose
`comparison` is not one of `>= > <= < =`. Unknown fields are refused. A new topic is a change to this record.

Researchers check their files before they hand them in:
`cd backend && uv run python -m app.adapters.law_index validate app/laws` (exit 1 and the file's error on a bad file).

**Retrieval** (`app/adapters/law_index.py`, stdlib `sqlite3`, no new dependency): at start every clause goes into
one in-memory SQLite FTS5 table, `tokenize='unicode61 remove_diacritics 2'` (case and accents folded: "Fluchtweg",
"fluchtweg", "Flüchtweg" match), columns `summary_en`, `keywords`, `heading` (+ `heading_en`), `text_en`, `text`,
`law` (titles and number), ranked by BM25 with column weights 4, 4, 2, 1, 1, 1: the English summary and keywords
written for search count above the long statute text. The query is user or model text: each word (`\w+`) of 3+
letters, minus a short English stopword list (`a an the do i is to of for in on my we when what how need`) and
repeats, becomes a quoted prefix term `"word"*`, at most 20 (QA lawkb-3/4, 2026-11-14: `"a"*` matched nearly every
clause and buried the one the question's key words find, and 250 such terms took a second under the index lock);
clauses with every word (AND) come first, then any word (OR) fills the limit
(a short clause sharing one common word must not outrank the one that has them all; fi-law, 2026-11-14). An
old-wording clause (id with `-anhang-`: a law's Anhang keeps the wording before an amendment, which applies only
where a commune has not adapted) comes after every current hit of both groups (QA lawkb-1, 2026-11-14). The
match is passed as a bound parameter, so `"`, `*`, `NEAR`, `-`, `AND` are
plain words and can neither break nor steer the MATCH syntax; the prefix makes "Fluchtweg" find "Fluchtwege" and
"bedroom" find "bedrooms". A search covers one pack (the project's country), optionally one topic.

- `search(pack, query, topic=None, limit=5) -> [{id, law_id, ref, title_en, summary_en, url, score}]`
  (`title_en` is the law's, `score` = -bm25, higher is better)
- `clause(id) -> the clause, plus law_id, law_number, law_title, law_title_en, url, language, checked, status_note`
- `toc(pack) -> [{law_id, number, title_en, clauses, topics}]`

**API** (additive to v1, 0007's error shape; docs/API.md "Building law"):

- `GET /api/laws` -> `{packs: [{id, laws: [toc entry]}]}`, both packs always listed, `laws: []` while empty.
- `GET /api/laws/{pack}/search?q=&topic=&limit=` -> `{pack, query, hits}`; `q` 1-500 characters, `topic` from
  the closed list, `limit` 1-20 (default 5); an unknown pack is 404 `unknown-pack` (the pack ids are 0009's).
- `GET /api/laws/clauses/{clause_id}` -> the clause as `clause()`; an unknown id is 404 `not-found`.

**Tools for the model** (`app/adapters/law_tools.py`, OpenAI function-calling JSON, the shape
`app/adapters/openvlm/client.py` sends): `search_law(pack, query, topic?)` and `get_clause(clause_id)`, whose
descriptions tell the model to search before it states a rule, to read the clause before quoting it, and to cite
`ref` and `url`; `run_tool(index, name, arguments)` runs one call and returns JSON text, an `{"error": ...}` object
for an unknown tool, bad arguments or an unknown clause, so the model can correct itself. `law_prompt(index, pack)`
is the always-in-prompt part: the pack's table of contents, one line per law, kept under ~1.5k tokens (tested on 30
laws; past the budget the last laws are left out with a line saying how many).

## Alternatives considered

- The whole corpus in the prompt: thousands of clauses in three languages is hundreds of thousands of tokens per
  question, paid on every call, slower, and long contexts bury the one subsection that matters. The table of
  contents (one line per law) tells the model what exists; search fetches the few clauses a question needs.
- Embeddings / a vector store now: a new dependency and a model to host or call, for a corpus of a few thousand
  short clauses that each carry a hand-written English summary and keywords in English and the original language,
  which is what makes BM25 work across languages. Add vectors only when a measured query set (questions with the
  clause a person expects) shows BM25 missing; the index's interface stays.
- One file per pack, or a database file in git: a law per file keeps researchers' edits apart and reviewable; the
  index is rebuilt at start in well under a second at this size.
- Extending 0009's rule packs: those are checkable limits with an op each; most law is not checkable and needs
  search, not a check engine. A clause's `limits` and `drawing_checkable` mark the ones a rule pack could add.

## Consequences

- A project's pack (`fi`, `ch-zh`) chooses the law the AI sees; a new country is a folder of law files.
- The researchers' files gate the start like rule packs: a broken file is found at once, naming the file.
- `text` is verbatim and `text_en` ours and unofficial; the screen and the model must say a translation is ours.
  No SIA or other paid standard is quoted (public MIT repo).
- Not done here: wiring the tools into a chat loop (the answering path has no LLM tool loop yet), and a measured
  query set; revisit retrieval when that set exists.
