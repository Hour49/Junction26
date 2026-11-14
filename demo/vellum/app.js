// Vellum clickable demo: state, routes, header, and screens 1 (drop), 2 + 9-12 (reading), 3 (conflicts), 5 (workspaces).
// Screen 4 (ask) is in ask.js. All data and counts come from data.js.
(function () {
  'use strict';
  const V = window.VData, P = window.VPlan, esc = P.esc;
  const TOTAL = V.STEPS.reduce((s, x) => s + x.secs, 0);
  const TICK_MS = 1400;

  // S.p is the one workspace of this demo session (null before an upload).
  const S = { p: null, signer: '', src: null };  // src: the open source preview {k: 'c' | 'i', id, i}
  const app = document.getElementById('app');

  const many = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  const hhmm = (ms) => new Date(ms).toTimeString().slice(0, 5);
  const ICON_CHECK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

  function newProject(analysed) {
    const now = Date.now();
    const conflicts = {};
    for (const c of V.CONFLICTS) conflicts[c.id] = { mode: c.ai === null ? 'open' : 'ai', pick: null };
    if (V.resetReadAsPlan) V.resetReadAsPlan();
    // calls / rap: a person's relevance calls and "read it as a floor plan" per triaged file (triage.js)
    S.p = { started: analysed ? now - TOTAL * 1000 : now, doneLogged: false, conflicts, history: [], turns: [], chat: [], chatRef: {}, di: 0, checks: {},
      calls: {}, rap: {}, rapDone: {}, issueFilter: { kind: null, state: null }, issues: {} };
    log(S.p.started, 'up', 'Uploaded the archive', `${V.ARCHIVE} · ${V.FILES.length} files`);
    logDone();
  }

  function log(at, kind, title, detail) { S.p.history.push({ at, kind, title, detail }); }

  // When the reading finishes: one event for it and one per conflict the AI settled by itself.
  function logDone() {
    const p = S.p;
    if (!p || p.doneLogged || !progress().done) return;
    p.doneLogged = true;
    const at = p.started + TOTAL * 1000, aside = V.FILES.filter((f) => !f.drawing).length;
    log(at, 'run', 'Analysis done', `${many(V.DRAWINGS.length, 'drawing')} ready, ${many(aside, 'file')} set aside, ${many(V.CONFLICTS.length, 'conflict')} found`);
    for (const c of V.CONFLICTS) {
      if (c.ai !== null) log(at, 'cf', `Conflict settled by the AI: ${c.title}`, `AI decision approved · ${V.variantLabels(c)[c.ai]}`);
      else log(at, 'cf', `Conflict waiting for you: ${c.title}`, 'The rules could not decide');
    }
  }

  const elapsed = () => (S.p ? (Date.now() - S.p.started) / 1000 : 0);
  const progress = () => V.progress(elapsed(), V.FILES, V.DRAWINGS.length);
  // what triage.js and issues.js derive from: the reading's end, the calls, and the conflict modes
  const ctx = () => ({ done: progress().done, calls: S.p.calls, rap: S.p.rap, conflicts: S.p.conflicts, now: Date.now(), project: window.VTriage.projectOf(V) });

  // The reading of each conflict now: the AI's while approved, the person's pick, else unsettled (null).
  function picks() {
    const out = {};
    for (const c of V.CONFLICTS) {
      const st = S.p.conflicts[c.id];
      out[c.id] = st.mode === 'ai' ? c.ai : st.mode === 'own' ? (st.custom ? { custom: st.custom } : st.pick) : null;
    }
    return out;
  }

  // ---------- routing ----------
  const PANELS = ['unpack', 'identify', 'normalise', 'extract', 'check'];
  function route() {
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
    const name = parts[0] || 'home';
    if (name === 'ingest' && PANELS.includes(parts[1])) return { name: 'advanced', panel: parts[1] };
    if (name === 'file' && /^\d+$/.test(parts[1] || '')) return { name: 'file', n: parts[1] };
    if (name === 'conflicts' || name === 'issues') return { name: 'ingest' };  // both live under the finished reading now
    return { name: ['ingest', 'chat', 'documents', 'ask', 'workspaces'].includes(name) ? name : 'home' };
  }

  function header(r) {
    const views = [['ingest', 'Ingest', '#/ingest'], ['chat', 'Chat', '#/chat'], ['documents', 'Documents', '#/documents']];
    const cur = r.name === 'advanced' || r.name === 'file' ? 'ingest' : r.name;
    const nav = S.p && r.name !== 'home' && r.name !== 'workspaces'
      ? `<nav class="seg" aria-label="Views">${views.map(([k, label, href]) => {
        const n = k === 'documents' ? needsYou() : 0, inner = n ? `${label}<span class="badge" aria-hidden="true">${n}</span>` : label;
        const aria = n ? ` aria-label="${label}, ${many(n, 'issue')} to answer"` : '';
        return k === cur ? `<span aria-current="page"${aria}>${inner}</span>` : `<a class="press" href="${href}"${aria}>${inner}</a>`;
      }).join('')}</nav>` : '';
    return `<header class="top"><div class="top-in" style="${r.name === 'workspaces' ? 'max-width:1280px' : ''}">
      <a class="brand" href="#/" aria-label="Vellum, start page"><img src="vellum-logo.png" alt="" width="44" height="44"><strong>Vellum</strong></a>
      ${nav}
      <div class="top-right"><a class="pill-link press" href="#/workspaces"${r.name === 'workspaces' ? ' aria-current="page"' : ''}>Workspaces</a></div>
    </div></header>`;
  }

  // Slots: parts of a screen refreshed by the clock without re-rendering the rest (so animations keep running).
  let slots = {};
  function render() {
    const r = route();
    if (r.name !== 'home' && r.name !== 'workspaces' && !S.p) newProject(true);
    slots = {};
    const screen = { home: homeScreen, ingest: ingestScreen, advanced: advancedScreen, documents: documentsScreen,
      chat: window.VChat.screen, ask: window.VAsk.screen, workspaces: workspacesScreen, file: window.VFiles.traceScreen}[r.name](r);
    app.innerHTML = header(r) + screen + srcModal();
    fill();
    if (S.src) app.querySelector('.modal-card .btn-close').focus();
  }
  function fill() {
    for (const name of Object.keys(slots)) {
      const el = app.querySelector(`[data-slot="${name}"]`);
      if (!el) continue;
      const html = slots[name]();
      if (el.__html !== html) { el.innerHTML = html; el.__html = html; }
    }
  }

  // ---------- 1 drop ----------
  function homeScreen() {
    const tags = ['IFC models', 'DXF · DWG', 'Vector PDF · SVG', 'PNG · JPG scans', 'ZIP archives'];
    return `<main class="w1120 home">
      <h1 class="hero">Every answer, pointed at the drawing.</h1>
      <section class="drop" aria-label="Drop drawings or an archive">
        <div class="drop-zone" data-drop>
          <span class="icon-tile" aria-hidden="true"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#3d5a4f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4"/><path d="M7.5 8.5L12 4l4.5 4.5"/><path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></svg></span>
          <p style="font-size:24px;font-weight:600;letter-spacing:-0.015em">Drop drawings or a .zip here</p>
          <div class="row-wrap">
            <button class="btn btn-primary press" data-act="choose">Choose files</button>
            <button class="btn btn-plain press" data-act="sample" style="font-size:15px">Try a sample</button>
            <input type="file" multiple hidden data-files aria-label="Choose drawing files">
          </div>
          <p class="small">This demo plays its real sample from the Stoa dataset, whatever you drop or choose.</p>
        </div>
        <div class="row-wrap" style="gap:8px">${tags.map((t) => `<span class="tag">${t}</span>`).join('')}</div>
      </section>
    </main>`;
  }

  // ---------- 2 reading, simple ----------
  function titleRow(view) {
    slots.kicker = () => (progress().done
      ? `<span class="kicker ok"><span class="dot" aria-hidden="true"></span>Analysis done</span>`
      : `<span class="kicker"><span class="dot pulse" aria-hidden="true"></span>Analysing now</span>`);
    const seg = view === 'simple'
      ? '<span aria-current="page">Simple</span><a class="press" href="#/ingest/unpack">Advanced</a>'
      : '<a class="press" href="#/ingest">Simple</a><span aria-current="page">Advanced</span>';
    return `<div class="title-row"><div><span data-slot="kicker"></span><h1>${esc(V.ARCHIVE)}</h1></div>
      <div class="seg" role="group" aria-label="View">${seg}</div></div>`;
  }

  function stat(label, value) { return `<div><dt>${label}</dt><dd>${value}</dd></div>`; }
  const secs = () => `${Math.round(Math.min(elapsed(), TOTAL))} s`;

  function doneRow() {
    const pr = progress();
    if (!pr.done) return '';
    const open = V.CONFLICTS.filter((c) => S.p.conflicts[c.id].mode === 'open').length;
    const found = V.CONFLICTS.length ? `${many(V.CONFLICTS.length, 'conflict')} found${open ? `, ${open} needs you` : ''}.` : 'No conflicts found.';
    const iss = needsYou();
    return `<div class="done-row"><span>${many(V.DRAWINGS.length, 'drawing')} ready.${V.CONFLICTS.length ? ' Conflicts are below.' : ''}${iss ? ` <a href="#/documents">${many(iss, 'issue')} in Documents</a> need${iss === 1 ? 's' : ''} you.` : ''}</span></div>`;
  }

  function ingestScreen() {
    slots.top = () => {
      const pr = progress(), pct = Math.round(pr.frac * 100), st = V.STEPS[Math.min(pr.step, 7)];
      return `<div style="display:flex;flex-direction:column;gap:4px"><span class="small" style="font-weight:500">${pr.done ? 'All 8 steps done' : `Step ${pr.step + 1} of 8`}</span><h2>${pr.done ? 'Ready' : st.name}</h2></div>
        <div class="ring" role="img" aria-label="${pct} percent done"><svg width="96" height="96" viewBox="0 0 96 96" aria-hidden="true"><circle cx="48" cy="48" r="40" fill="none" stroke="#eef0ef" stroke-width="8"/><circle cx="48" cy="48" r="40" fill="none" stroke="#3d5a4f" stroke-width="8" stroke-linecap="round" stroke-dasharray="251.3" stroke-dashoffset="${(251.3 * (1 - pr.frac)).toFixed(1)}"/></svg><span>${pct}<small style="font-size:13px;color:var(--v-muted)">%</small></span></div>`;
    };
    slots.stats = () => {
      const pr = progress();
      return stat('Elapsed', secs()) + stat('Files through', `${pr.through} / ${pr.files}`) + stat('Drawings ready', `${pr.ready} / ${pr.drawings}`) + stat('Set aside', pr.aside);
    };
    slots.steps = () => {
      const pr = progress();
      return V.STEPS.map((s, i) => {
        const done = pr.done || i < pr.step, now = !pr.done && i === pr.step;
        const ico = done ? `<span class="s-done" role="img" aria-label="done">${ICON_CHECK}</span>`
          : now ? '<span role="img" aria-label="working" style="display:flex"><svg class="spin" width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="8.5" fill="none" stroke="#dbe4df" stroke-width="2.5"/><path d="M11 2.5a8.5 8.5 0 0 1 8.5 8.5" fill="none" stroke="#3d5a4f" stroke-width="2.5" stroke-linecap="round"/></svg></span>'
            : '<span class="s-wait" role="img" aria-label="waiting"></span>';
        return `<li class="${now ? 'now' : ''}"><div class="step-row">${ico}<span style="${now ? 'font-weight:600' : done ? 'color:var(--v-text-2)' : 'color:var(--v-muted)'}">${s.name}</span>${now ? `<span class="small">${s.hint}</span>` : ''}</div>${now ? '<div data-slot="bar" style="margin:10px 0 2px 34px;display:flex;align-items:center;gap:12px"></div>' : ''}</li>`;
      }).join('');
    };
    slots.bar = () => {
      const pct = Math.round(progress().within * 100);
      return `<div class="bar"><div style="width:${pct}%"></div></div><span class="small" style="font-variant-numeric:tabular-nums">${pct}% of this step</span>`;
    };
    slots.done = doneRow;
    return `<main class="w820">${titleRow('simple')}
      <section class="card" aria-label="Progress"><div class="prog-top" data-slot="top"></div>
        <dl class="stats" data-slot="stats"></dl><ol class="steps" data-slot="steps"></ol><div data-slot="done"></div></section>
      ${progress().done ? conflictsBlock() + chatCta() : ''}</main>`;
  }

  // ---------- 9-12 reading, advanced ----------
  const k = () => Math.floor(Date.now() / TICK_MS);
  const cycle = (list) => list[k() % list.length];
  // the newest line on top, older ones fade
  const logLines = (lines) => lines.map((_, i) => lines[(k() - i + lines.length * 100) % lines.length]).slice(0, 4)
    .map((t, i) => `<li style="opacity:${(1 - i * 0.22).toFixed(2)}">${esc(t)}</li>`).join('');
  const sayLine = (lines) => `<span class="live" style="display:block">${esc(cycle(lines))}</span>`;
  const DRAWING_FILES = V.FILES.filter((f) => f.drawing);
  const WHY = { DXF: 'read exactly from its layers and blocks.', DWG: 'converted to DXF once, then read exactly from its layers and blocks.',
    'IFC model': 'a BIM model: every door and window is already a typed object.', 'Vector PDF': 'vector lines inside the PDF, so measurements stay exact.',
    'PNG rendering': 'a raster rendering of the floor, so it is read from the image.',
    'PNG scan': 'a scan has no CAD layers, so rooms and openings are read from the image.', 'JPG scan': 'a scan has no CAD layers, so rooms and openings are read from the image.',
    'JPG photo': 'a phone photo at low resolution: rooms are readable, openings less sure.' };

  function panelState(panel) {
    const pr = progress(), idx = V.STEPS.map((s, i) => [s.panel, i]).filter(([p]) => p === panel).map(([, i]) => i);
    if (pr.done || pr.step > Math.max(...idx)) return 'done';
    return pr.step >= Math.min(...idx) ? 'now' : 'next';
  }

  function advancedScreen(r) {
    slots.rail = () => {
      const pr = progress();
      return V.STEPS.map((s, i) => {
        const st = pr.done || i < pr.step ? 'done' : i === pr.step ? 'now' : 'wait';
        return `<a class="press ${st}" href="#/ingest/${s.panel}"${s.panel === r.panel ? ' aria-current="step"' : ''}><span class="r-ico ${st}${st === 'now' ? ' pulse' : ''}" role="img" aria-label="${st === 'wait' ? 'waiting' : st === 'now' ? 'working' : 'done'}">${st === 'done' ? ICON_CHECK : ''}</span>${s.name}</a>`;
      }).join('');
    };
    const HEAD = { unpack: 'Unpacking', identify: 'Identifying and routing', normalise: 'Normalising', extract: 'Extracting', check: 'Cross-checking' };
    slots.now = () => {
      const st = panelState(r.panel);
      return st === 'now' ? '<span class="kicker"><span class="spin-ico spin" aria-hidden="true"></span>Now</span>'
        : st === 'done' ? '<span class="kicker ok">Done · replaying what this step did</span>' : '<span class="kicker" style="color:var(--v-muted)">Next</span>';
    };
    slots.done = doneRow;
    const body = { unpack: unpackPanel, identify: identifyPanel, normalise: normalisePanel, extract: extractPanel, check: checkPanel }[r.panel]();
    return `<main class="w1040">${titleRow('advanced')}
      <nav class="rail" aria-label="Steps" data-slot="rail"></nav>
      <section class="card" aria-label="${HEAD[r.panel]}"><div class="panel">
        <div class="panel-fig">${body.fig}</div>
        <div class="panel-txt"><span data-slot="now"></span><h2>${HEAD[r.panel]}</h2>
          <p class="say" aria-live="polite" data-slot="say"></p><ol class="log" aria-label="Log" data-slot="log"></ol></div>
      </div><dl class="stats" data-slot="stats"></dl><div data-slot="done"></div></section>
      ${progress().done ? conflictsBlock() + chatCta() : ''}</main>`;
  }

  function unpackPanel() {
    const say = ['Opening the zip and listing what is inside, without unpacking anything yet.',
      'Checking every path stays inside the archive, so nothing can be written elsewhere.',
      'Watching the size: a small zip that unpacks to gigabytes is stopped here.',
      'Skipping system files like __MACOSX, they are not drawings.'];
    slots.say = () => sayLine(say);
    // a later page of a multi-page PDF is split off as a file of its own (#156)
    const page = (f) => { const m = f.path.match(/^(.*)#p(\d+)\.pdf$/); return m ? `page ${m[2]} of ${m[1]}.pdf, as a PDF of its own` : `open  ${f.path} · ${f.size}`; };
    slots.log = () => logLines(V.FILES.map(page));
    slots.name = () => `<span class="live">${esc(cycle(V.FILES).path)}</span>`;
    slots.stats = () => {
      const pr = progress();
      return stat('Elapsed', secs()) + stat('Files opened', `${pr.done || pr.step > 0 ? pr.files : pr.through} / ${pr.files}`)
        + stat('Set aside', pr.aside) + stat('Drawings found', pr.done || pr.step >= 2 ? pr.drawings : '…');
    };
    const strip = V.FILES.map(P.thumb).join('');
    return { fig: `<div class="film-box" aria-hidden="true"><div class="film">${strip}${strip}</div><div class="film-frame"></div></div><p class="film-name" data-slot="name"></p>` };
  }

  function identifyPanel() {
    const T = window.VTriage, triaged = V.FILES.filter((f) => T.of(f.path));
    const lines = DRAWING_FILES.map((f) => [f.path, WHY[f.kind]])
      .concat(triaged.map((f) => [f.path, `not a floor plan (${T.CLASS_LABEL[T.classOf(f.path)]}): kept, set aside, not read. File triage is a preview.`]))
      .concat(triaged.length ? [[null, 'Without triage, ingest keeps only 15 of 214 non-plans out of the floor-plan readers (Bogdan\'s measurement).']] : []);
    slots.say = () => { const [path, why] = cycle(lines); return `<span class="live" style="display:block">${path ? `<span class="mono">${esc(path)}</span>: ` : ''}${esc(why)}</span>`; };
    slots.log = () => logLines(DRAWING_FILES.map((f) => `route ${f.lane === 'CAD' ? 'cad   ' : 'vision'} ${f.path}`)
      .concat(triaged.map((f) => `identify ${f.path}; triage: ${T.classOf(f.path)}, ${T.of(f.path).register.kind} (preview)`)));
    slots.fig = () => {
      const f = cycle(DRAWING_FILES), d = V.drawing(f.drawing), look = P.lookOfFile(f.kind);
      return `<div class="fig" style="background:${look === 'cad' ? '#16181d' : '#f3eedd'}">${P.plain(d, look, `${f.path}, being identified`)}
        <div class="chips" aria-hidden="true"><span class="chip-f" style="left:0;top:0">${esc(f.kind)}</span><span class="chip-f" style="right:0;top:0;animation-delay:.7s">${esc(f.size)}</span>
        <span class="chip-f" style="left:0;bottom:0;animation-delay:1.4s">${f.lane === 'CAD' ? 'Exact geometry inside' : 'Pixels only'}</span></div></div>
        <div class="lanes"><div class="lane${f.lane === 'CAD' ? ' on' : ''}"><strong>CAD geometry</strong><span>${f.lane === 'CAD' ? 'This file goes here' : 'Exact, from layers and blocks'}</span>${f.lane === 'CAD' ? '<span class="travel-bar" style="--d:220px" aria-hidden="true"></span>' : ''}</div>
        <div class="lane${f.lane === 'Vision' ? ' on' : ''}"><strong>Vision model</strong><span>${f.lane === 'Vision' ? 'This file goes here' : 'For scans and photos'}</span>${f.lane === 'Vision' ? '<span class="travel-bar" style="--d:220px" aria-hidden="true"></span>' : ''}</div></div>`;
    };
    slots.stats = () => {
      const pr = progress(), seen = pr.done || pr.step > 2;
      const n = (lane) => (seen ? DRAWING_FILES.filter((f) => f.lane === lane).length : '…');
      return stat('Elapsed', secs()) + stat('To CAD', n('CAD')) + stat('To vision', n('Vision')) + stat('Set aside', pr.aside);
    };
    return { fig: '<div data-slot="fig"></div>' };
  }

  // The drawing as uploaded next to it normalised: upright, one view, scale known. A Stoa image is shown as it is.
  function normalisePanel() {
    const d = V.extractFacts().drawing;
    slots.say = () => sayLine(['Turning each sheet upright.', 'Splitting each sheet into its views: the plan, the legend, the title block.',
      'Finding the scale: the scale bar or the ratio in the title block.']);
    slots.log = () => logLines(DRAWING_FILES.map((f) => `normalise ${f.path}`));
    slots.stats = () => stat('Elapsed', secs()) + stat('Files', DRAWING_FILES.length) + stat('Drawings ready', `${progress().ready} / ${V.DRAWINGS.length}`) + stat('Set aside', progress().aside);
    const uploaded = P.plain(d, 'scan', `${d.name}, as uploaded`);
    const note = 'Already upright: the dataset renders it from the floor geometry.';
    return { fig: `<div class="nfigs"><figure><figcaption class="small">As uploaded</figcaption><div class="fig">${uploaded}</div></figure>
      <figure><figcaption class="small">Normalised</figcaption><div class="fig" style="background:#fafafc">${P.plain(d, 'clean', `${d.name}, normalised`)}</div><p class="small" style="margin:0">${note}</p></figure></div>` };
  }

  function extractPanel() {
    const { drawing: d, rooms, doors, windows } = V.extractFacts();
    slots.say = () => sayLine(['Finding rooms: closed loops of wall with a label inside.', 'Reading the labels inside each room.',
      'Finding doors: a gap in a wall with a leaf and a swing arc.', 'Finding windows: thin double lines set into outside walls.',
      'Measuring: the scale in the title block turns pixels into metres.']);
    slots.log = () => logLines(rooms.map((r) => `room  ${r.label}${r.area === undefined ? '' : ` ${r.area.toFixed(1)} m²`}`).concat([`door  ${doors} found`, `window ${windows} found`]));
    slots.stats = () => stat('Rooms', rooms.length) + stat('Doors', doors) + stat('Windows', windows) + stat('Drawings ready', `${progress().ready} / ${V.DRAWINGS.length}`);
    if (d.image) {
      return { fig: `<div class="fig" style="position:relative">${P.plain(d, 'scan', `${d.name}, being read`)}<div class="sweep" aria-hidden="true" style="position:absolute;left:0;right:0;top:0;height:40px;background:linear-gradient(rgba(61,90,79,0),rgba(61,90,79,0.3));border-bottom:2px solid #3d5a4f"></div></div><p class="small mono" style="margin-top:10px">${esc(d.name)}</p>` };
    }
    const [vx, vy, vw] = V.layoutOf(d).view;
    const finds = rooms.map((r, i) => `<g class="find-g" style="animation-delay:${(i * 0.45).toFixed(2)}s"><rect x="${r.x + 5}" y="${r.y + 5}" width="${r.w - 10}" height="${r.h - 10}" rx="6" fill="rgba(61,90,79,0.12)" stroke="#3d5a4f" stroke-width="2.5"/><rect x="${r.x + 11}" y="${r.y + 11}" width="${r.label.length * 7 + 16}" height="20" rx="10" fill="#3d5a4f"/><text x="${r.x + 19}" y="${r.y + 25}" font-family="Inter, system-ui, sans-serif" font-size="12" font-weight="600" fill="#fff">${esc(r.label)}</text></g>`).join('');
    const plan = P.plain(d, 'scan', `${d.name}, rooms being found`).replace('</svg>', `${finds}<g class="sweep"><rect x="${vx}" y="${vy}" width="${vw}" height="40" fill="rgba(61,90,79,0.18)"/><rect x="${vx}" y="${vy + 39}" width="${vw}" height="2" fill="#3d5a4f"/></g></svg>`);
    return { fig: `<div class="fig">${plan}</div><p class="small mono" style="margin-top:10px">${esc(d.name)}.jpg</p>` };
  }

  function checkPanel() {
    const pairs = V.crossChecks(), agree = pairs.filter((p) => p.agree).length;
    const say = pairs.map((q) => (q.agree ? `Counting ${q.quantity}s on ${q.drawing} twice, by two independent methods. Both say ${q.a}.`
      : `${q.drawing}: ${q.a} ${q.quantity}s against ${q.b}. They disagree, so this goes to you as a conflict.`));
    slots.say = () => sayLine(say);
    slots.log = () => logLines(pairs.map((q) => `check ${q.drawing} ${q.quantity}s ${q.a}/${q.b} ${q.agree ? 'ok' : 'CONFLICT'}`));
    const FAM = ['Doors per drawing', 'Windows per drawing', 'Rooms per drawing', 'Net floor area', 'Marks on every answer', 'Second count per answer'];
    if (!pairs.length) {
      slots.say = () => sayLine(['Each value is checked by a second, independent reading where one exists.', 'This drawing has no second reading here, so nothing is cross-checked.']);
      slots.log = () => '<li>check  no second reading</li>';
      slots.fig = () => `<div class="ready"><strong style="font-size:15px">Answers ready before you ask</strong><ul>${FAM.map((n) => `<li class="on"><i aria-hidden="true"></i>${n}</li>`).join('')}</ul></div>`;
      slots.stats = () => stat('Elapsed', secs()) + stat('Counts checked', 0) + stat('Agree', 0) + stat('Conflicts', V.CONFLICTS.length);
      return { fig: '<div data-slot="fig"></div>' };
    }
    slots.fig = () => {
      const q = cycle(pairs), on = Math.min(FAM.length, 2 + (k() % (FAM.length + 2)));
      return `<div class="pair"><div class="pair-box"><span class="small">First reading</span><b class="live">${q.a}</b><span style="font-size:13px;color:var(--v-text-2)">${q.quantity}s</span></div>
        <div class="pair-link" aria-hidden="true"><span style="--d:72px;position:absolute;left:-24px;top:0;width:24px;height:3px;background:#3d5a4f"></span></div>
        <div class="pair-box"><span class="small">Second, independent count</span><b class="live">${q.b}</b><span class="mono" style="font-size:13px;color:var(--v-text-2)">${esc(q.drawing)}</span></div></div>
        <div class="verdict live ${q.agree ? 'ok' : 'warn'}">${q.agree ? 'They agree. Kept as the answer.' : 'They disagree. Sent to Settle the conflicts.'}</div>
        <div class="ready"><strong style="font-size:15px">Answers ready before you ask</strong><ul>${FAM.map((n, i) => `<li class="${i < on ? 'on' : ''}"><i aria-hidden="true"></i>${n}</li>`).join('')}</ul></div>`;
    };
    slots.stats = () => stat('Elapsed', secs()) + stat('Counts checked', pairs.length) + stat('Agree', agree) + stat('Conflicts', V.CONFLICTS.length);
    return { fig: '<div data-slot="fig"></div>' };
  }

  // ---------- 3 conflicts ----------
  function conflictsBlock() {
    const p = S.p, pk = picks();
    const settled = V.CONFLICTS.filter((c) => pk[c.id] !== null).length, locked = settled < V.CONFLICTS.length;
    const ai = V.CONFLICTS.filter((c) => c.ai !== null).length;
    const PILL = { ai: ['Approved', 'ok'], own: ['Your choice', 'acc'], modify: ['Choosing', 'grey'], open: ['Needs you', 'warn'] };
    const TIP = { ai: 'Approved: the AI settled this by the rules and it is in use. Modify it if you disagree.',
      own: 'Your choice: you picked this variant, and it overrides the AI.', modify: 'Choosing: tap the variant that is right, or cancel to keep the AI decision.',
      open: 'Needs you: the rules could not decide. Pick a variant before you open the workspace.' };
    const ordered = V.CONFLICTS.filter((c) => c.ai !== null).concat(V.CONFLICTS.filter((c) => c.ai === null));
    const cards = ordered.map((c, n) => {
      const st = p.conflicts[c.id], unsolved = c.ai === null, choosing = st.mode === 'modify' || st.mode === 'open';
      const labels = V.variantLabels(c);
      let plan = '';
      if (c.src) plan = srcFigure('c', c.id, c.src);
      else if (unsolved) {
        const d = V.drawing(c.drawing), a = V.answer(d.id, `How many ${c.quantity}s?`, pk);
        plan = `<figure class="c-plan"><div>${P.answerPlan(d, a, { flagged: new Map([[c.element, 'in question']]) })}</div><figcaption>${esc(c.where || "Amber: the balcony glazing in question")}, on <span class="mono">${esc(d.name)}</span>.</figcaption></figure>`;
      }
      const tiles = c.variants.map((v, i) => {
        const chosen = pk[c.id] === i;
        return `<button class="tile press${chosen ? ' chosen' : choosing ? ' choosing' : ''}" aria-pressed="${chosen}"${choosing ? ` data-act="pick" data-c="${c.id}" data-i="${i}"` : ' aria-disabled="true"'}>
          <span class="tile-top"><span>Variant ${i + 1}${c.ai === i ? ' · AI decision' : ''}</span>${chosen ? `<span class="check-dot" role="img" aria-label="in use">${ICON_CHECK}</span>` : ''}</span>
          <span class="tile-val">${esc(labels[i])}</span><span class="tile-src">${esc(v.src)}</span></button>`;
      }).join('');
      const action = { ai: '', own: st.custom ? `You answered: “${esc(st.custom)}”.` : `You chose variant ${(st.pick ?? 0) + 1}${!unsolved && st.pick !== c.ai ? ', over the AI decision' : ''}.`, modify: 'Tap the right variant.', open: 'Tap the right variant.' }[st.mode];
      return `<article class="conflict" aria-label="Conflict ${n + 1}"><div class="c-head"><div>
          <span style="font-size:12px;font-weight:500;color:var(--v-muted)">Conflict ${n + 1} of ${V.CONFLICTS.length} · ${unsolved ? 'unsolved' : 'solved by the AI'}</span>
          <h2>${esc(c.title)}</h2><span class="mono" style="font-size:12px;color:var(--v-muted)">${esc(c.files)}</span></div>
          <span class="tip" tabindex="0"><span class="pill ${PILL[st.mode][1]}">${PILL[st.mode][0]}</span><span role="tooltip" class="tip-body">${TIP[st.mode]}</span></span></div>
        ${plan}<div class="vars" role="group" aria-label="Variants">${tiles}</div>
        ${choosing ? `<form class="c-own" data-own="${c.id}"><label class="small" for="own-${c.id}">Or type your own answer</label>
          ${(c.suggest || []).length ? `<div class="chips-row">${c.suggest.map((x) => `<button type="button" class="qchip press" data-act="own-fill" data-c="${c.id}" data-v="${esc(x)}">${esc(x)}</button>`).join('')}</div>` : ''}
          <div class="c-own-row"><input id="own-${c.id}" name="v" maxlength="140" autocomplete="off" placeholder="${esc(c.placeholder || 'Your answer')}"><button class="btn btn-primary press" type="submit">Use my answer</button></div></form>` : ''}
        <details class="why"><summary><svg class="chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6e6e73" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>${unsolved ? 'Why the AI could not decide' : `Why the AI chose variant ${c.ai + 1}`}</summary>
          <ol>${c.rules.map((x) => `<li>${esc(x)}</li>`).join('')}</ol><p>${esc(c.why)}</p></details>
        <div class="c-foot"><span>${action}</span>${st.mode === 'ai' || st.mode === 'own' ? `<button class="btn btn-soft press" data-act="modify" data-c="${c.id}">Modify</button>` : ''}
          ${st.mode === 'modify' ? `<button class="btn btn-plain press" data-act="cancel" data-c="${c.id}">Cancel</button>` : ''}
          ${st.mode === 'own' && !unsolved ? `<button class="btn btn-plain press" data-act="use-ai" data-c="${c.id}">Use the AI decision</button>` : ''}</div></article>`;
    }).join('');
    const count = (m) => V.CONFLICTS.filter((c) => p.conflicts[c.id].mode === m).length;
    const needs = V.CONFLICTS.length - count('ai') - count('own');
    const summary = [[count('ai'), 'settled by the AI'], [count('own'), 'settled by you'], [needs, needs === 1 ? 'needs you' : 'need you']]
      .filter(([n]) => n).map(([n, t]) => `${n} ${t}.`).join(' ');
    return `<section class="flow" aria-label="Conflicts"><div><h2 class="list-h">${V.CONFLICTS.length ? `${V.CONFLICTS.length} conflicts found` : 'No conflicts found'}</h2><p class="muted" style="margin:0">${summary || 'Nothing to settle: no drawing was read twice with different values.'}</p></div>
      ${V.CONFLICTS.length ? `<div style="display:flex;align-items:center;gap:12px"><div class="segs" aria-hidden="true">${V.CONFLICTS.map((_, i) => `<span class="${i < settled ? 'on' : ''}"></span>`).join('')}</div>
        <span style="font-size:13px;font-weight:500;color:var(--v-text-2)" role="status">${settled} of ${V.CONFLICTS.length} settled</span></div>` : ''}
      ${cards}</section>`;
  }

  // ---------- sources: the real image cropped to the place in question, outlined and numbered ----------
  function sourceFig(src, i) {
    const f = V.FILES.find((x) => x.path === src.files[i]), [vx, vy, vw, vh] = src.view;
    const pct = (n) => `${n.toFixed(2)}%`;
    const pos = ([x, y, w, h]) => `left:${pct((x - vx) / vw * 100)};top:${pct((y - vy) / vh * 100)};width:${pct(w / vw * 100)};height:${pct(h / vh * 100)}`;
    return `<div class="src" style="aspect-ratio:${(vw * src.ratio / vh).toFixed(3)}"><img src="${esc(f.image)}" alt="${esc(f.path)}" loading="lazy" style="left:${pct(-vx / vw * 100)};top:${pct(-vy / vh * 100)};width:${pct(10000 / vw)}">${src.marks.map((m, n) => `<span class="hl" style="${pos(m.box)}"><b>${n + 1}</b></span>`).join('')}</div>`;
  }
  const legend = (src) => `<ol class="hl-legend">${src.marks.map((m, n) => `<li><b>${n + 1}</b><span>${esc(m.label)}</span></li>`).join('')}</ol>`;
  const srcFigure = (k, id, src) => `<figure class="c-plan"><div>${sourceFig(src, 0)}</div><figcaption>${legend(src)}
    <button class="btn btn-soft press" data-act="src-open" data-k="${k}" data-id="${id}">Show source</button></figcaption></figure>`;

  function srcModal() {
    if (!S.src) return '';
    const src = (S.src.k === 'c' ? V.CONFLICTS : V.ISSUES).find((x) => x.id === S.src.id).src, n = src.files.length, i = ((S.src.i % n) + n) % n;
    const arrow = (d, path, label) => `<button class="round press ref-arrow ${d < 0 ? 'l' : 'r'}" data-act="src-move" data-d="${d}" aria-label="${label}"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1d1d1f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg></button>`;
    return `<div class="modal" data-act="src-close"><div class="modal-card" role="dialog" aria-modal="true" aria-label="Source: ${esc(src.files[i])}" data-act="noop">
      <div class="modal-head"><span class="mono" style="font-size:14px;font-weight:600;overflow-wrap:anywhere">${esc(src.files[i])}${n > 1 ? ` <span class="small">· ${i + 1} of ${n}</span>` : ''}</span>
        <button class="btn btn-soft press btn-close" data-act="src-close">Close</button></div>
      <div class="ref-view">${sourceFig(src, i)}${n > 1 ? arrow(-1, 'M15 6l-6 6 6 6', 'Previous source') + arrow(1, 'M9 6l6 6-6 6', 'Next source') : ''}</div>${legend(src)}</div></div>`;
  }

  // the issues a person answers (stoa.js ISSUES); notes are shown but never counted
  const issueState = (x) => S.p.issues[x.id] || {};
  const needsYou = () => (S.p && progress().done ? (V.ISSUES || []).filter((x) => x.severity !== 'note' && !issueState(x).answer).length : 0);
  function issuesSection() {
    const list = V.ISSUES || [];
    if (!progress().done || !list.length) return '';
    const head = { fails_rule: 'Fails a rule', needs_person: 'Needs a person' };
    const rows = ['fails_rule', 'needs_person', 'note'].flatMap((sev) => list.filter((x) => x.severity === sev)).map((x, n) => {
      const st = issueState(x), note = x.severity === 'note', fi = V.FILES.findIndex((f) => f.path === x.file);
      const pill = note ? ['Note', 'grey'] : st.answer ? ['Answered', 'ok'] : [head[x.severity], 'warn'];
      const answer = note ? '' : st.answer && !st.editing
        ? `<div class="c-foot"><span>You answered: “${esc(st.answer)}”.</span><button class="btn btn-soft press" data-act="issue-edit" data-id="${x.id}">Change</button></div>`
        : `<form class="c-own" data-issue="${x.id}"><label class="small" for="own-${x.id}">Your answer</label>
          ${(x.suggest || []).length ? `<div class="chips-row">${x.suggest.map((v) => `<button type="button" class="qchip press" data-act="own-fill" data-c="${x.id}" data-v="${esc(v)}">${esc(v)}</button>`).join('')}</div>` : ''}
          <div class="c-own-row"><input id="own-${x.id}" name="v" maxlength="140" autocomplete="off" placeholder="${esc(x.placeholder || 'Your answer')}" value="${esc(st.answer || '')}"><button class="btn btn-primary press" type="submit">Use my answer</button>${st.answer ? `<button type="button" class="btn btn-plain press" data-act="issue-cancel" data-id="${x.id}">Cancel</button>` : ''}</div></form>`;
      return `<li class="card iss-card"><div class="iss-top"><span class="iss-n" aria-hidden="true">${n + 1}</span><span class="pill ${pill[1]}">${pill[0]}</span>
          <span class="small mono" style="overflow-wrap:anywhere">${esc(x.file)}</span>${fi >= 0 ? `<a class="small" style="margin-left:auto" href="#/file/${fi}">Open the file</a>` : ''}</div>
        <p class="iss-why">${esc(x.why)}</p>${x.src ? srcFigure('i', x.id, x.src) : ''}${answer}</li>`;
    }).join('');
    const open = needsYou();
    return `<section class="flow" aria-label="Issues"><div><h2 class="list-h">Issues</h2><p class="muted" style="margin:0">${open ? `${many(open, 'issue')} need${open === 1 ? 's' : ''} your answer.` : 'Every issue is answered.'} Notes are for your information.</p></div>
      <ol class="iss">${rows}</ol></section>`;
  }

  function chatCta() {
    const locked = V.CONFLICTS.some((c) => picks()[c.id] === null);
    return `<div class="chat-cta">${locked
      ? '<button class="btn press" disabled aria-describedby="chat-why">Start a new chat</button><span id="chat-why" class="small">Settle the conflicts that need you first.</span>'
      : '<a class="btn btn-primary press" href="#/chat">Start a new chat</a><a class="small" href="#/ask">Open the workspace</a>'}</div>`;
  }

  // every ingested document: the drawings and every file, each opening its trace
  function documentsScreen() {
    slots.files = window.VFiles.lists;
    return `<main class="w820"><div class="title-row"><div><span class="kicker ok">${esc(V.ARCHIVE)}</span><h1>Documents</h1>
      <p class="muted" style="margin:0">${many(V.FILES.length, 'file')} ingested, ${many(V.DRAWINGS.length, 'drawing')} read from them</p></div></div>
      ${issuesSection()}<div class="lists" data-slot="files"></div></main>`;
  }

  // ---------- 5 workspaces ----------
  function workspacesScreen() {
    const p = S.p;
    if (!p) {
      return `<main class="w1280"><div class="title-row"><div><h1>Your workspaces</h1><p class="muted" style="margin:0">0 workspaces on this server</p></div></div>
        <section class="card empty"><p style="margin:0;font-size:17px;font-weight:600">No workspace yet</p><p class="muted" style="margin:0">Drop drawings or try the sample to start one.</p><a class="btn btn-primary press" href="#/">New workspace</a></section></main>`;
    }
    const pr = progress(), pk = picks(), open = V.CONFLICTS.filter((c) => pk[c.id] === null).length;
    const signed = Object.values(p.checks).filter((c) => c.state === 'checked').length;
    const pill = !pr.done ? ['Reading', 'grey'] : ['Ready', 'ok'];
    const glyph = { up: '↑', run: '✓', cf: '⇄', ask: '?', sign: '✓' };
    const events = p.history.slice().sort((a, b) => a.at - b.at).map((e) => `<li><span class="small" style="padding-top:3px;font-variant-numeric:tabular-nums">${hhmm(e.at)}</span>
      <span class="glyph g-${e.kind}" aria-hidden="true">${glyph[e.kind]}</span><span style="display:flex;flex-direction:column;gap:1px;min-width:0">
      <span style="font-size:15px;font-weight:500;overflow-wrap:anywhere">${esc(e.title)}</span><span class="small" style="overflow-wrap:anywhere">${esc(e.detail)}</span></span></li>`).join('');
    return `<main class="w1280"><div class="title-row"><div><h1>Your workspaces</h1><p class="muted" style="margin:0">1 workspace on this server</p></div>
        <a class="btn btn-primary press" href="#/">New workspace</a></div>
      <div class="acc-wrap"><section class="ws-list" aria-label="Workspaces">
          <div class="ws"><span class="ws-top"><span class="mono" style="font-size:13px;font-weight:600">${esc(V.ARCHIVE)}</span>
            <span style="display:flex;gap:6px;flex-wrap:wrap"><span class="pill ${pill[1]}">${pill[0]}</span>${pr.done && open ? `<span class="pill warn">${open} conflict open</span>` : ''}</span></span>
            <span class="small">Archive · ${many(V.FILES.length, 'file')} · ${many(V.DRAWINGS.length, 'drawing')}</span><span class="small">Today, ${hhmm(p.started)}</span></div>
        </section>
        <section class="card hist" aria-label="History"><div class="hist-head"><div style="display:flex;flex-direction:column;gap:4px;min-width:0">
            <span style="font-size:12px;font-weight:500;color:var(--v-muted)">Archive · created today, ${hhmm(p.started)}</span><h2>${esc(V.ARCHIVE)}</h2></div>
            <a class="btn btn-soft press" href="${pr.done ? '#/ask' : '#/ingest'}">Open workspace</a></div>
          <dl class="stats" style="border-bottom:1px solid #f0f1f0">${stat('Files', V.FILES.length)}${stat('Drawings', V.DRAWINGS.length)}${stat('Questions', p.turns.length + p.chat.length)}${stat('Signed off', signed)}</dl>
          <h3 style="margin:20px 24px 4px;font-size:15px">History</h3><ol class="events">${events}</ol></section></div></main>`;
  }

  // ---------- events ----------
  const ACTIONS = {
    choose: () => { app.querySelector('[data-files]').click(); return false; },
    sample: () => start(),
    pick: (el) => { const c = V.CONFLICTS.find((x) => x.id === el.dataset.c), i = Number(el.dataset.i);
      S.p.conflicts[c.id] = { mode: 'own', pick: i };
      log(Date.now(), 'cf', `Conflict settled: ${c.title}`, `Your choice · ${V.variantLabels(c)[i]}${c.ai !== null && c.ai !== i ? ', over the AI decision' : ''}`); },
    'src-open': (el) => { S.src = { k: el.dataset.k, id: el.dataset.id, i: 0 }; },
    'src-move': (el) => { S.src.i += Number(el.dataset.d); },
    'src-close': () => { S.src = null; },
    noop: () => false,
    'issue-edit': (el) => { S.p.issues[el.dataset.id] = { ...S.p.issues[el.dataset.id], editing: true }; },
    'issue-cancel': (el) => { S.p.issues[el.dataset.id] = { ...S.p.issues[el.dataset.id], editing: false }; },
    'own-fill': (el) => { const inp = document.getElementById(`own-${el.dataset.c}`); inp.value = el.dataset.v; inp.focus(); return false; },
    // Modify keeps what was in use, so Cancel can put it back (a person's choice keeps Modify, never "Change")
    modify: (el) => { const id = el.dataset.c; S.p.conflicts[id] = { mode: 'modify', pick: null, back: S.p.conflicts[id] }; },
    cancel: (el) => { const id = el.dataset.c; S.p.conflicts[id] = S.p.conflicts[id].back; },
    'use-ai': (el) => { const c = V.CONFLICTS.find((x) => x.id === el.dataset.c);
      S.p.conflicts[c.id] = { mode: 'ai', pick: null };
      log(Date.now(), 'cf', `AI decision restored: ${c.title}`, `AI decision approved · ${V.variantLabels(c)[c.ai]}`); },
  };
  document.addEventListener('submit', (ev) => {
    const iid = ev.target.dataset && ev.target.dataset.issue;
    if (iid) {
      ev.preventDefault();
      const text = ev.target.v.value.trim().slice(0, 140), x = V.ISSUES.find((y) => y.id === iid);
      if (!text) return;
      S.p.issues[iid] = { answer: text };
      log(Date.now(), 'sign', `Issue answered: ${x.file.split('/').pop()}`, text);
      render();
      return;
    }
    const id = ev.target.dataset && ev.target.dataset.own;
    if (!id) return;
    ev.preventDefault();
    const text = ev.target.v.value.trim().slice(0, 140), c = V.CONFLICTS.find((x) => x.id === id);
    if (!text) return;
    S.p.conflicts[id] = { mode: 'own', pick: null, custom: text };
    log(Date.now(), 'cf', `Conflict settled: ${c.title}`, `Your answer · ${text}`);
    render();
  });
  function start() { newProject(false); location.hash = '#/ingest'; return false; }

  app.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el || el.getAttribute('aria-disabled') === 'true') return;
    const act = el.dataset.act;
    const fn = ACTIONS[act] || window.VAsk.actions[act] || window.VChat.actions[act] || window.VFiles.actions[act] || window.VIssues.actions[act];
    if (fn && fn(el, ev) !== false) render();
  });
  app.addEventListener('keydown', (ev) => {
    const el = ev.target.closest('[role="button"][data-act]');
    if (el && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); el.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
  });
  app.addEventListener('change', (ev) => { if (ev.target.matches('[data-files]') && ev.target.files.length) start(); });
  app.addEventListener('dragover', (ev) => { const z = ev.target.closest('[data-drop]'); if (z) { ev.preventDefault(); z.classList.add('over'); } });
  app.addEventListener('dragleave', (ev) => { const z = ev.target.closest('[data-drop]'); if (z) z.classList.remove('over'); });
  app.addEventListener('drop', (ev) => { if (ev.target.closest('[data-drop]')) { ev.preventDefault(); start(); } });
  window.addEventListener('hashchange', () => { S.src = null; render(); window.scrollTo(0, 0); });
  document.addEventListener('keydown', (ev) => {
    if (!S.src) return;
    if (ev.key === 'Escape') S.src = null;
    else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') S.src.i += ev.key === 'ArrowLeft' ? -1 : 1;
    else return;
    render();
  });
  setInterval(() => {
    if (!S.p) return;
    const was = S.p.doneLogged; logDone();
    // the end of the reading or of a re-read changes whole screens (issues, trace, the drawing switcher)
    // a file's trace follows its re-read: queued, running, ready (R7-c-1)
    const rapNow = Object.keys(S.p.rap).map((p) => window.VTriage.rapState(p, ctx())).join();
    const rapMoved = rapNow !== S.p.rapSeen;
    S.p.rapSeen = rapNow;
    if (window.VFiles.tick() || (was !== S.p.doneLogged && ['workspaces', 'ingest', 'advanced', 'documents', 'file'].includes(route().name)) || (rapMoved && route().name === 'file')) render(); else fill();
  }, 250);

  window.VApp = { S, render, log, picks, esc, hhmm, progress, ctx };
  document.addEventListener('DOMContentLoaded', render);
})();
