// File triage (decision 0010), a PREVIEW: triage is off in the shipped config until its classifier passes its check
// (Bogdan, #152 c6877019522). This one unit holds the per-file register row, description and relevance, their words,
// the pure lines the screens show and the trace's triage card, so the coming shapes (#152 c6876983657) swap here.
// Loaded as a plain script (global VTriage) and by node --test.
(function (root) {
  'use strict';
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  const RULE = 'related when a printed word of 4 or more letters matches the project\'s name, its other file or folder names, or the text on its plans; unsure when it shows a building but nothing matches; else unrelated';
  const METHOD = 'local classifier; a preview with illustrative values';

  // Synthetic: four images of the sample upload, in the shapes of 0010 §8 (#152 c6877087844). register: the
  // sheet-register row; description: the describer's form. Relevance is not stored: relevanceOf applies the rule.
  // Stoa mode hands its own (VData.TRIAGE: real scans, each with image, credit and example: a hand-picked example).
  const SAMPLE = {
    'elevations/south-elevation.png': { picture: 'elevation',
      register: { kind: 'elevation', has_floor_plan: false, photo_of_sheet: false, scale_shown: 'ratio_text', quality: 'good', method: METHOD },
      description: { text: 'The south face of a four-storey block, drawn straight on, with a title block.', what_it_is: 'drawing', shows_building: true,
        visible_text: 'Harbour Block\nSouth elevation 1:100',
        detail: 'A line drawing of a building face seen straight on. Four rows of six windows, an entrance in the middle of the ground row, a flat roof with a parapet. The title block in the lower right names the building and the view and gives a scale. No rooms are drawn, so there is nothing to count.' } },
    'photos/site.jpg': { picture: 'photo',
      register: { kind: 'photograph', has_floor_plan: false, photo_of_sheet: false, scale_shown: 'none', quality: 'fair', method: METHOD },
      description: { text: 'A phone photo of an empty paved yard with a parked bicycle and a fence.', what_it_is: 'photograph', shows_building: false,
        visible_text: '', detail: 'Taken outdoors in daylight. A paved yard fills the lower half, a wooden fence runs across the middle and a bicycle leans on it. No building, no drawing and no printed text.' } },
    'misc/poster.jpg': { picture: 'poster',
      register: { kind: 'not_architecture', has_floor_plan: false, photo_of_sheet: false, scale_shown: 'none', quality: 'good', method: METHOD },
      description: { text: 'A poster for a concert: a large title, a time and a drawing of a violin.', what_it_is: 'artwork', shows_building: false,
        visible_text: 'Autumn Concert\n7 pm', detail: 'A printed poster on a dark background. The title is set large across the top, a time below it, and a violin drawn in light lines fills the middle.' } },
    'scans/annex-sketch.jpg': { picture: 'sketch',
      register: { kind: 'site_plan_or_map', has_floor_plan: false, photo_of_sheet: false, scale_shown: 'none', quality: 'poor', method: METHOD },
      description: { text: 'A faint pencil sketch of a few rooms with a north arrow; it could be a sketch plan or a site layout.', what_it_is: 'drawing', shows_building: true,
        visible_text: 'Annex\nKitchen', detail: 'Pencil on paper, scanned light. Three rectangles drawn freehand share walls; one is labelled Kitchen. Short gaps in the walls may be doors. The word Annex is written above.' } },
  };
  const TRIAGE = root.VData && root.VData.TRIAGE ? root.VData.TRIAGE : SAMPLE;

  const CLASS_LABEL = { floor_plan: 'a floor plan', other_drawing: 'another kind of drawing', not_drawing: 'not a drawing' };
  const VERDICT = {
    related: { pill: '✓ Related', sentence: 'Related to this project', word: 'related' },
    unrelated: { pill: '✕ Not related', sentence: 'Not related to this project', word: 'not related' },
    unsure: { pill: '? Unsure', sentence: 'Unsure whether it belongs to this project', word: 'unsure' },
    none: { pill: '– Not judged' },
  };
  const NOT_JUDGED = 'not judged yet: the project is still being read';
  const PREVIEW_TIP = 'File triage is coming (decision 0010). It is off in today\'s demo config until its classifier passes its check.';
  // drawing words too: "floor plan" printed on a sheet says nothing about which project it belongs to
  const STOP = new Set(['this', 'that', 'with', 'from', 'have', 'there', 'their', 'what', 'page', 'sheet', 'drawing', 'scale',
    'floor', 'plan', 'plans', 'site', 'section', 'elevation', 'archive', 'level', 'north', 'south', 'east', 'west']);

  const of = (path) => TRIAGE[path] || null;
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const kindWords = (k) => k.replace(/_/g, ' ');
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
    return { name: V.ARCHIVE, paths: V.FILES.map((f) => f.path), plan: labels.join(' ') };
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
  const notPlans = (files, ctx) => files.filter((f) => of(f.path) && classOf(f.path) !== 'floor_plan' && !ctx.rap[f.path]).length;
  function notPlansLine(n) {
    return n === 0 ? 'No image set aside as not a floor plan' : n === 1 ? '1 not a floor plan: kept, not read' : `${n} not floor plans: kept, not read`;
  }

  // The file row's line: { text, pill (null: none), by (null: no call) }. hasDrawing: the re-read found a drawing.
  function rowLine(path, ctx, hasDrawing) {
    const r = ctx.rap[path];
    if (r) {
      const st = rapState(path, ctx);
      return { text: st === 'ready' && !hasDrawing ? 'read as a floor plan: no rooms or openings were found on it' : `Read as a floor plan on ${r.by}'s call`, pill: null, by: null };
    }
    const v = verdictOf(path, ctx), call = ctx.calls[path];
    return { text: `Not a floor plan: ${CLASS_LABEL[classOf(path)]} · ${kindWords(of(path).register.kind)}`, pill: VERDICT[v || 'none'].pill, by: call ? call.by : null };
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

  // ---------- pictures (synthetic, drawn here; no real file) ----------
  function picture(path, label) {
    const t = of(path), a = `role="img" aria-label="${esc(label)}"`, box = 'viewBox="0 0 400 280" class="plan tri-pic"';
    if (t.image) return `<img class="plan tri-pic" src="${esc(t.image)}" alt="${esc(label)}">`;
    if (t.picture === 'elevation') {
      let w = '';
      for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) if (!(r === 3 && (c === 2 || c === 3))) w += `<rect x="${92 + c * 36}" y="${52 + r * 40}" width="20" height="24" fill="none" stroke="#1d1d1f" stroke-width="1.5"/>`;
      return `<svg ${box} ${a}><rect width="400" height="280" fill="#fff"/><rect x="80" y="36" width="230" height="182" fill="none" stroke="#1d1d1f" stroke-width="2.5"/><rect x="76" y="30" width="238" height="8" fill="none" stroke="#1d1d1f" stroke-width="1.5"/>${w}<rect x="180" y="178" width="30" height="40" fill="none" stroke="#1d1d1f" stroke-width="1.5"/><line x1="40" y1="218" x2="360" y2="218" stroke="#1d1d1f" stroke-width="3"/><g font-family="Inter, system-ui, sans-serif" fill="#48484a"><rect x="268" y="232" width="120" height="40" fill="none" stroke="#1d1d1f"/><text x="276" y="248" font-size="11" font-weight="600">Harbour Block</text><text x="276" y="264" font-size="10">South elevation · 1:100</text></g></svg>`;
    }
    if (t.picture === 'photo') {
      let fence = '';
      for (let x = 10; x < 400; x += 26) fence += `<rect x="${x}" y="96" width="18" height="74" fill="#a07c55"/>`;
      return `<svg ${box} ${a}><rect width="400" height="280" fill="#c9dbe6"/><rect y="150" width="400" height="130" fill="#9a9a93"/>${fence}<rect y="110" width="400" height="8" fill="#8a6a46"/><g fill="none" stroke="#2c3140" stroke-width="4"><circle cx="170" cy="200" r="28"/><circle cx="250" cy="200" r="28"/><path d="M170 200l30-40h36l14 40M200 160l-6-14h-12M236 160l6-12h12M210 200l-10-40"/></g></svg>`;
    }
    if (t.picture === 'poster') {
      return `<svg ${box} ${a}><rect width="400" height="280" fill="#2b2140"/><g font-family="Georgia, serif" fill="#f3e9d2" text-anchor="middle"><text x="200" y="58" font-size="34" font-weight="700">Autumn Concert</text><text x="200" y="88" font-size="18">7 pm</text></g><g fill="none" stroke="#f3e9d2" stroke-width="2.5"><ellipse cx="200" cy="200" rx="36" ry="44"/><ellipse cx="200" cy="142" rx="26" ry="28"/><line x1="200" y1="110" x2="200" y2="252"/><line x1="200" y1="110" x2="214" y2="98"/></g></svg>`;
    }
    // the sketch: the annex layout in the scan look (plan.js), since it really is a plan
    const P = root.VPlan, V = root.VData, d = V.READ_AS_PLAN && V.READ_AS_PLAN[path];
    return d && P ? P.plain(d, 'scan', label).replace('class="plan ', 'class="plan tri-pic ') : `<svg ${box} ${a}><rect width="400" height="280" fill="#f3eedd"/></svg>`;
  }

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
    const belong = `<div class="tri-part"><h3>Does it belong to this project?</h3><p><span class="pill ${v === 'related' ? 'ok' : v === 'unsure' ? 'warn' : 'grey'}">${vp.pill}</span>
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
      <p class="small">Kind: ${esc(kindWords(t.register.kind))}</p>
      <figure class="tri-fig">${picture(path, `${path} as uploaded`)}${t.credit ? `<figcaption class="small credit">Credit: ${esc(t.credit)}</figcaption>` : ''}</figure>
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
