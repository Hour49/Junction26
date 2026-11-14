// File triage (decision 0010), a PREVIEW: triage is off in the shipped config until its classifier passes its check
// (Bogdan, #152 c6877019522). This one unit holds the per-file register row, description and relevance, their words,
// the pure lines the screens show and the trace's triage card, so the coming shapes (#152 c6876983657) swap here.
// Loaded as a plain script (global VTriage) and by node --test.
(function (root) {
  'use strict';
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const RULE = 'related when a printed word of 4 or more letters matches the project\'s name, its other file or folder names, or the text on its plans; unsure when it shows a building but nothing matches; else unrelated';
  
  // Per real file (stoa.js hands VData.TRIAGE): register row, description (each a hand-picked example: what a person
  // saw on the real image), image and credit. Relevance is not stored: relevanceOf applies the rule.
  const TRIAGE = (root.VData && root.VData.TRIAGE) || {};

  const CLASS_LABEL = { floor_plan: 'a floor plan', other_drawing: 'another kind of drawing', not_drawing: 'not a drawing' };
  const VERDICT = {
    related: { pill: '✓ Related', sentence: 'Related to this project', word: 'related' },
    unrelated: { pill: '✕ Not related', sentence: 'Not related to this project', word: 'not related' },
    unsure: { pill: '? Unsure', sentence: 'Unsure whether it belongs to this project', word: 'unsure' },
    none: { pill: '– Not judged' },
  };
  const NOT_JUDGED = 'not judged yet: the project is still being read';
  const PREVIEW_TIP = 'File triage is coming. It is switched off in today\'s app until its classifier passes its check.';
  // drawing words too: "floor plan" printed on a sheet says nothing about which project it belongs to
  const STOP = new Set(['this', 'that', 'with', 'from', 'have', 'there', 'their', 'what', 'page', 'sheet', 'drawing', 'scale',
    'floor', 'plan', 'plans', 'site', 'section', 'elevation', 'archive', 'level', 'north', 'south', 'east', 'west']);

  const of = (path) => TRIAGE[path] || null;
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  // the register's kind in plain words (R7-c-8)
  const KIND_WORDS = { floor_plan: 'a floor plan', elevation: 'an elevation (a face of the building)', section: 'a section (a cut through the building)',
    site_plan_or_map: 'a site plan or map', cover_or_text_sheet: 'a cover or text page', photograph: 'a photo',
    not_architecture: 'a picture that is not of a building design', other: 'another kind of picture' };
  const kindWords = (k) => KIND_WORDS[k] || k.replace(/_/g, ' ');
  // 0010 §8: the class follows the register (unsure counts as a plan)
  function classOf(path) {
    const r = of(path).register;
    if (r.has_floor_plan || r.kind === 'floor_plan') return 'floor_plan';
    return ['photograph', 'not_architecture', 'cover_or_text_sheet', 'other'].includes(r.kind) ? 'not_drawing' : 'other_drawing';
  }

  // The project's words the rule compares with: its name, the other files' file and folder names, its plans' text.
  const wordsOf = (t) => (t.toLowerCase().match(/\p{L}{4,}/gu) || []).filter((w) => !STOP.has(w));
  function projectOf(V) {
    const labels = V.DRAWINGS.flatMap((d) => (V.layoutOf(d) ? V.rooms(d).map((r) => r.label) : []));
    return { name: [V.ARCHIVE, V.FLOOR_ID].filter(Boolean).join(' '), paths: V.FILES.map((f) => f.path), plan: labels.join(' ') };
  }
  // The relevance rule (0010 §8): related when it shows a building or a printed word matches; why names the match.
  function relevanceOf(path, project) {
    const d = of(path).description;
    const sources = [['the project name', new Set(wordsOf(project.name))],
      ['the other file and folder names', new Set(wordsOf(project.paths.filter((p) => p !== path).join(' ')))],
      ['the text on the plans', new Set(wordsOf(project.plan))]];
    const matched = [];
    for (const w of new Set(wordsOf(d.visible_text))) {
      const src = sources.find(([, set]) => set.has(w));
      if (src) matched.push(`"${d.visible_text.match(new RegExp(w, 'i'))[0]}" (${src[0]})`);
    }
    const rule = `rule: ${RULE}`;
    // #152 c6877132244: related only with a printed match; a building alone is unsure (a person decides)
    if (matched.length) return { verdict: 'related', why: `related: ${matched.map((m) => `${m} is printed on it`).join('; ')}`, matched_on: matched, plans: [], judge: rule };
    if (d.shows_building) return { verdict: 'unsure', why: 'unsure: it shows a building, but no printed word matches the project\'s name, its other file or folder names, or its plans', matched_on: [], plans: [], judge: rule };
    return { verdict: 'unrelated', why: 'unrelated: it shows no building, and no printed word matches the project\'s name, its other file or folder names, or its plans', matched_on: [], plans: [], judge: rule };
  }

  // ctx: { done (the project is read), calls {path: {verdict, by, at}}, rap {path: {by, at}} read as a plan, now (ms),
  // project (projectOf) }
  function verdictOf(path, ctx) {
    if (!of(path)) return null;
    const call = ctx.calls[path];
    return call ? call.verdict : ctx.done ? relevanceOf(path, ctx.project).verdict : null;
  }
  // The re-read of a file a person had read as a plan: queued, then running, then ready (about 3 s).
  function rapState(path, ctx) {
    const r = ctx.rap[path];
    if (!r) return null;
    const ms = ctx.now - r.at;
    return ms < 1000 ? 'queued' : ms < 3000 ? 'running' : 'ready';
  }
  // a file read as a plan counts once it has a drawing; one where the read found nothing stays set aside (R7-c-7)
  const notPlans = (files) => files.filter((f) => of(f.path) && classOf(f.path) !== 'floor_plan' && !f.drawing).length;
  function notPlansLine(n) {
    return n === 0 ? 'No image set aside as not a floor plan' : n === 1 ? '1 not a floor plan: kept, not read' : `${n} not floor plans: kept, not read`;
  }

  const pillClass = (v) => (v === 'related' ? 'ok' : v === 'unsure' ? 'warn' : 'grey');
  // The file row's line: { text, pill (null: none), tone (the pill's colour), by (null: no call) }. hasDrawing: the re-read found a drawing.
  function rowLine(path, ctx, hasDrawing) {
    const r = ctx.rap[path];
    if (r) {
      const st = rapState(path, ctx);
      return { text: st === 'ready' && !hasDrawing ? 'read as a floor plan: no rooms or openings were found on it' : `Read as a floor plan on ${r.by}'s call`, pill: null, by: null };
    }
    const v = verdictOf(path, ctx), call = ctx.calls[path];
    return { text: `Not a floor plan: ${CLASS_LABEL[classOf(path)]} · ${kindWords(of(path).register.kind)}`, pill: VERDICT[v || 'none'].pill, tone: pillClass(v), by: call ? call.by : null };
  }
  function callLine(path, ctx, time) {
    const call = ctx.calls[path];
    return `${VERDICT[call.verdict].sentence}: ${call.by}'s call, ${time}. The rule said: ${VERDICT[relevanceOf(path, ctx.project).verdict].word}.`;
  }

  // The file's unrelated_file issue (decision 0010 §5), or null: one per non-plan not related, plus any a person
  // called or had read as a plan. Unsure (needs a person) only with no plan in the project, which the sample never is.
  function issueOf(path, ctx) {
    const call = ctx.calls[path], r = ctx.rap[path];
    if (!of(path) || !ctx.done) return null;
    const rel = relevanceOf(path, ctx.project);
    if (rel.verdict === 'related' && !call && !r) return null;
    const said = call ? ` ${call.by} says it is ${VERDICT[call.verdict].word}.` : '';
    const read = r ? ` ${r.by} had it read as a floor plan.` : '';
    return { severity: rel.verdict === 'unsure' ? 'needs_person' : 'note', state: call || r ? 'settled' : 'open', reason: verdictOf(path, ctx),
      why: `Not a floor plan (${CLASS_LABEL[classOf(path)]}: ${kindWords(of(path).register.kind)}). ${cap(rel.why)}.${said}${read}` };
  }

  // ---------- pictures: the real image ----------
  const picture = (path, label) => `<img class="plan tri-pic" src="${esc(of(path).image)}" alt="${esc(label)}">`;

  // ---------- the trace's triage card ----------
  // ctx as above; signer: the typed name; time(ms) → "HH:MM".
  function card(path, ctx, signer, time) {
    const t = of(path), call = ctx.calls[path], r = ctx.rap[path], v = verdictOf(path, ctx), cls = CLASS_LABEL[classOf(path)];
    const pill = `<span class="tip" tabindex="0"><span class="pill acc">Preview</span><span role="tooltip" class="tip-body">${PREVIEW_TIP}</span></span>`;
    const head = r ? `<h2 class="tri-h">Read as a floor plan on ${esc(r.by)}'s call</h2><p class="small">Triage said: ${cls}.</p>` : `<h2 class="tri-h">Not a floor plan: ${cls}</h2>`;
    const d = t.description;
    const seen = d.visible_text
      ? `<details class="tri-more"><summary>Text printed on it</summary><p class="small tri-text">${esc(d.visible_text)}</p></details>` : '<p class="small">No text printed on it.</p>';
    const vp = v ? VERDICT[v] : VERDICT.none, rel = ctx.done ? relevanceOf(path, ctx.project) : null;
    const belong = `<div class="tri-part"><h3>Does it belong to this project?</h3><p><span class="pill ${pillClass(v)}">${vp.pill}</span>
      ${v ? `<span>${vp.sentence}</span>` : `<span class="muted">${NOT_JUDGED}</span>`}</p>
      ${rel ? `<p class="small">The rule says ${esc(rel.why)}.</p>${rel.matched_on.length ? `<p class="small">Matched on: ${esc(rel.matched_on.join(', '))}</p>` : ''}<p class="small muted">Decided by the ${esc(rel.judge)}.</p>` : ''}</div>`;
    const off = signer.trim() ? '' : ' disabled';
    let callHtml = '';
    if (ctx.done && call) {
      callHtml = `<div class="tri-part"><p>${esc(callLine(path, ctx, time(call.at)))}</p><div class="dc-btns"><button class="btn btn-plain press" data-act="tri-undo" data-path="${esc(path)}">Undo the call</button></div></div>`;
    } else if (ctx.done) {
      callHtml = `<div class="tri-part"><h3>Your call</h3><div class="tri-call"><label class="signas">Your name<input data-name value="${esc(signer)}" placeholder="Your name" maxlength="100" autocomplete="name"></label>
        <button class="btn btn-soft press" data-act="tri-call" data-v="related" data-path="${esc(path)}" data-needs-name${off}>It is related</button>
        <button class="btn btn-soft press" data-act="tri-call" data-v="unrelated" data-path="${esc(path)}" data-needs-name${off}>It is not related</button></div>
        <p class="small">Your call replaces the suggestion and settles this file's issue. It does not read the file as a plan.</p></div>`;
    }
    const read = r
      ? `<p class="small">${esc(r.by)} had it read as a floor plan, ${time(r.at)}.</p>`
      : ctx.done ? `<div class="tri-part"><button class="btn btn-plain press" data-act="tri-read" data-path="${esc(path)}" data-needs-name${off}>Read it as a floor plan</button>
        <p class="small">If it is a floor plan after all, it is read like any drawing. This can't be undone.</p></div>` : '';
    return `<section class="card tri" aria-label="Is it a floor plan?"><div class="tri-top">${head}${pill}</div>
      <p class="small">What triage saw: ${esc(kindWords(t.register.kind))}</p>
      <figure class="tri-fig">${picture(path, `${path} as uploaded`)}</figure>
      <div class="tri-part"><h3>What is on it</h3><p>${esc(d.text)}</p>${seen}
        <details class="tri-more"><summary>Full description (${t.example ? EXAMPLE : 'a model\'s description, not checked by a person'})</summary><p class="small">${esc(d.detail)}</p></details></div>
      ${belong}${callHtml}${read}</section>`;
  }

  // ---------- the project chat's question about a set-aside elevation (a preview) ----------
  // The backend keeps a non-plan's description for later AI use and does not answer from it yet: this shows what such
  // an answer could pull. The quote is the description's sentences holding a word of the question, else its summary.
  const EXAMPLE = 'a hand-picked example written for this demo: what a person saw, not a model\'s output';
  const ASKS_ELEVATION = /\b(elevation|fa[cç]ade)s?\b/i;
  const QSTOP = new Set(['many', 'does', 'building', 'show', 'shows', 'house', 'have', 'there']);
  const stem = (w) => w.replace(/(ies|s)$/, '');
  function described(question, files) {
    if (!ASKS_ELEVATION.test(question)) return null;
    const f = files.find((x) => of(x.path) && of(x.path).register.kind === 'elevation');
    if (!f) return null;
    const d = of(f.path).description, want = wordsOf(question).filter((w) => !QSTOP.has(w) && !ASKS_ELEVATION.test(w)).map(stem);
    const said = `${d.text} ${d.detail}`.split(/(?<=\.)\s+/).filter((x) => want.some((w) => x.toLowerCase().includes(w)));
    return { path: f.path, quote: said.length ? said.slice(0, 2).join(' ') : d.text, matched: said.length > 0, example: !!of(f.path).example };
  }

  const API = { TRIAGE, CLASS_LABEL, VERDICT, RULE, NOT_JUDGED, PREVIEW_TIP, of, classOf, projectOf, relevanceOf, verdictOf, rapState,
    notPlans, notPlansLine, rowLine, callLine, issueOf, picture, card, described, kindWords, EXAMPLE };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.VTriage = API;
})(typeof window !== 'undefined' ? window : globalThis);
