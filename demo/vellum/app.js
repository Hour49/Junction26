// Vellum clickable demo: state, routes, header, and screens 1 (drop), 2 + 9-12 (reading), 3 (conflicts), 5 (workspaces).
// Screen 4 (ask) is in ask.js. All data and counts come from data.js.
(function () {
  'use strict';
  const V = window.VData, P = window.VPlan, esc = P.esc;
  const TOTAL = V.STEPS.reduce((s, x) => s + x.secs, 0);
  const TICK_MS = 1400;

  // S.p is the one workspace of this demo session (null before an upload).
  const S = { p: null, signer: '' };
  const app = document.getElementById('app');

  const hhmm = (ms) => new Date(ms).toTimeString().slice(0, 5);
  const ICON_CHECK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

  function newProject(analysed) {
    const now = Date.now();
    const conflicts = {};
    for (const c of V.CONFLICTS) conflicts[c.id] = { mode: c.ai === null ? 'open' : 'ai', pick: null };
    S.p = { started: analysed ? now - TOTAL * 1000 : now, doneLogged: false, conflicts, history: [], turns: [], di: 0, checks: {} };
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
    log(at, 'run', 'Analysis done', `${V.DRAWINGS.length} drawings ready, ${aside} files set aside, ${V.CONFLICTS.length} conflicts found`);
    for (const c of V.CONFLICTS) {
      if (c.ai !== null) log(at, 'cf', `Conflict settled by the AI: ${c.title}`, `AI decision approved · ${V.variantLabels(c)[c.ai]}`);
      else log(at, 'cf', `Conflict waiting for you: ${c.title}`, 'The rules could not decide');
    }
  }

  const elapsed = () => (S.p ? (Date.now() - S.p.started) / 1000 : 0);
  const progress = () => V.progress(elapsed());

  // The reading of each conflict now: the AI's while approved, the person's pick, else unsettled (null).
  function picks() {
    const out = {};
    for (const c of V.CONFLICTS) {
      const st = S.p.conflicts[c.id];
      out[c.id] = st.mode === 'ai' ? c.ai : st.mode === 'own' ? st.pick : null;
    }
    return out;
  }

  // ---------- routing ----------
  const PANELS = ['unpack', 'identify', 'extract', 'check'];
  function route() {
    const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
    const name = parts[0] || 'home';
    if (name === 'ingest' && PANELS.includes(parts[1])) return { name: 'advanced', panel: parts[1] };
    return { name: ['ingest', 'conflicts', 'ask', 'workspaces'].includes(name) ? name : 'home' };
  }

  function header(r) {
    const views = [['ingest', 'Ingest', '#/ingest'], ['conflicts', 'Conflicts', '#/conflicts'], ['ask', 'Engineer', '#/ask']];
    const cur = r.name === 'advanced' ? 'ingest' : r.name;
    const nav = S.p && r.name !== 'home' && r.name !== 'workspaces'
      ? `<nav class="seg" aria-label="Views">${views.map(([k, label, href]) => (k === cur
        ? `<span aria-current="page">${label}</span>` : `<a class="press" href="${href}">${label}</a>`)).join('')}</nav>` : '';
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
    const screen = { home: homeScreen, ingest: ingestScreen, advanced: advancedScreen, conflicts: conflictsScreen,
      ask: window.VAsk.screen, workspaces: workspacesScreen }[r.name](r);
    app.innerHTML = header(r) + screen + '<p class="foot">Clickable demo · synthetic data drawn in the browser, no backend, nothing read from a real file.</p>';
    fill();
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
          <p class="small">This demo plays its synthetic sample archive, whatever you drop or choose.</p>
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
    return `<div class="done-row"><span>${V.DRAWINGS.length} drawings ready. ${V.CONFLICTS.length} conflicts found${open ? `, ${open} needs you` : ''}.</span>
      <a class="btn btn-primary press" href="#/conflicts">Settle the conflicts</a></div>`;
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
        <dl class="stats" data-slot="stats"></dl><ol class="steps" data-slot="steps"></ol><div data-slot="done"></div></section></main>`;
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
    const HEAD = { unpack: 'Unpacking', identify: 'Identifying and routing', extract: 'Extracting', check: 'Cross-checking' };
    slots.now = () => {
      const st = panelState(r.panel);
      return st === 'now' ? '<span class="kicker"><span class="spin-ico spin" aria-hidden="true"></span>Now</span>'
        : st === 'done' ? '<span class="kicker ok">Done · replaying what this step did</span>' : '<span class="kicker" style="color:var(--v-muted)">Next</span>';
    };
    slots.done = doneRow;
    const body = { unpack: unpackPanel, identify: identifyPanel, extract: extractPanel, check: checkPanel }[r.panel]();
    return `<main class="w1040">${titleRow('advanced')}
      <nav class="rail" aria-label="Steps" data-slot="rail"></nav>
      <section class="card" aria-label="${HEAD[r.panel]}"><div class="panel">
        <div class="panel-fig">${body.fig}</div>
        <div class="panel-txt"><span data-slot="now"></span><h2>${HEAD[r.panel]}</h2>
          <p class="say" aria-live="polite" data-slot="say"></p><ol class="log" aria-label="Log" data-slot="log"></ol></div>
      </div><dl class="stats" data-slot="stats"></dl><div data-slot="done"></div></section></main>`;
  }

  function unpackPanel() {
    const say = ['Opening the zip and listing what is inside, without unpacking anything yet.',
      'Checking every path stays inside the archive, so nothing can be written elsewhere.',
      'Watching the size: a small zip that unpacks to gigabytes is stopped here.',
      'Skipping system files like __MACOSX, they are not drawings.'];
    slots.say = () => sayLine(say);
    slots.log = () => logLines(V.FILES.map((f) => `open  ${f.path} · ${f.size}`));
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
    slots.say = () => { const f = cycle(DRAWING_FILES); return `<span class="live" style="display:block"><span class="mono">${esc(f.path)}</span>: ${esc(WHY[f.kind])}</span>`; };
    slots.log = () => logLines(DRAWING_FILES.map((f) => `route ${f.lane === 'CAD' ? 'cad   ' : 'vision'} ${f.path}`));
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

  function extractPanel() {
    const d = V.drawing('ground-floor'), rooms = V.rooms(d);
    const doors = V.valueOf(V.marksFor(d, 'door', {}), 'door'), windows = V.valueOf(V.marksFor(d, 'window', {}), 'window');
    slots.say = () => sayLine(['Finding rooms: closed loops of wall with a label inside.', 'Reading the labels inside each room.',
      'Finding doors: a gap in a wall with a leaf and a swing arc.', 'Finding windows: thin double lines set into outside walls.',
      'Measuring: the scale in the title block turns pixels into metres.']);
    slots.log = () => logLines(rooms.map((r) => `room  ${r.label} ${r.area.toFixed(1)} m²`).concat([`door  ${doors} found`, `window ${windows} found`]));
    slots.stats = () => stat('Rooms', rooms.length) + stat('Doors', doors) + stat('Windows', windows) + stat('Drawings ready', `${progress().ready} / ${V.DRAWINGS.length}`);
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
  function conflictsScreen() {
    const p = S.p, pk = picks();
    const settled = V.CONFLICTS.filter((c) => pk[c.id] !== null).length, locked = settled < V.CONFLICTS.length;
    const ai = V.CONFLICTS.filter((c) => c.ai !== null).length;
    const PILL = { ai: ['Approved', 'ok'], own: ['Your choice', 'acc'], modify: ['Choosing', 'grey'], open: ['Needs you', 'warn'] };
    const TIP = { ai: 'Approved: the AI settled this by the rules and it is in use. Modify it if you disagree.',
      own: 'Your choice: you picked this variant, and it overrides the AI.', modify: 'Choosing: tap the variant that is right, or cancel to keep the AI decision.',
      open: 'Needs you: the rules could not decide. Pick a variant before you open the workspace.' };
    const cards = V.CONFLICTS.map((c, n) => {
      const st = p.conflicts[c.id], unsolved = c.ai === null, choosing = st.mode === 'modify' || st.mode === 'open';
      const labels = V.variantLabels(c);
      let plan = '';
      if (unsolved) {
        const d = V.drawing(c.drawing), a = V.answer(d.id, `How many ${c.quantity}s?`, pk);
        plan = `<figure class="c-plan"><div>${P.answerPlan(d, a, { flagged: new Map([[c.element, 'in question']]) })}</div><figcaption>Amber: the balcony glazing in question, on <span class="mono">${esc(d.name)}</span>.</figcaption></figure>`;
      }
      const tiles = c.variants.map((v, i) => {
        const chosen = pk[c.id] === i;
        return `<button class="tile press${chosen ? ' chosen' : choosing ? ' choosing' : ''}" aria-pressed="${chosen}"${choosing ? ` data-act="pick" data-c="${c.id}" data-i="${i}"` : ' aria-disabled="true"'}>
          <span class="tile-top"><span>Variant ${i + 1}${c.ai === i ? ' · AI decision' : ''}</span>${chosen ? `<span class="check-dot" role="img" aria-label="in use">${ICON_CHECK}</span>` : ''}</span>
          <span class="tile-val">${esc(labels[i])}</span><span class="tile-src">${esc(v.src)}</span></button>`;
      }).join('');
      const action = { ai: '', own: `You chose variant ${(st.pick ?? 0) + 1}${!unsolved && st.pick !== c.ai ? ', over the AI decision' : ''}.`, modify: 'Tap the right variant.', open: 'Tap the right variant.' }[st.mode];
      const reset = st.mode === 'modify' ? 'Cancel' : unsolved ? 'Change' : 'Use the AI decision';
      return `<article class="conflict" aria-label="Conflict ${n + 1}"><div class="c-head"><div>
          <span style="font-size:12px;font-weight:500;color:var(--v-muted)">Conflict ${n + 1} of ${V.CONFLICTS.length} · ${unsolved ? 'unsolved' : 'solved by the AI'}</span>
          <h2>${esc(c.title)}</h2><span class="mono" style="font-size:12px;color:var(--v-muted)">${esc(c.files)}</span></div>
          <span class="tip" tabindex="0"><span class="pill ${PILL[st.mode][1]}">${PILL[st.mode][0]}</span><span role="tooltip" class="tip-body">${TIP[st.mode]}</span></span></div>
        ${plan}<div class="vars" role="group" aria-label="Variants">${tiles}</div>
        <details class="why"><summary><svg class="chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6e6e73" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>${unsolved ? 'Why the AI could not decide' : `Why the AI chose variant ${c.ai + 1}`}</summary>
          <ol>${c.rules.map((x) => `<li>${esc(x)}</li>`).join('')}</ol><p>${esc(c.why)}</p></details>
        <div class="c-foot"><span>${action}</span>${st.mode === 'ai' ? `<button class="btn btn-soft press" data-act="modify" data-c="${c.id}">Modify</button>` : ''}
          ${st.mode === 'modify' || st.mode === 'own' ? `<button class="btn btn-plain press" data-act="reset" data-c="${c.id}">${reset}</button>` : ''}</div></article>`;
    }).join('');
    const open = V.CONFLICTS.length - ai;
    return `<main class="w820"><div class="title-row"><div>
        <span class="kicker ok">${esc(V.ARCHIVE)} · ${V.DRAWINGS.length} drawings ready</span>
        <h1>${V.CONFLICTS.length} conflicts found</h1><p class="muted" style="margin:0">The AI settled ${ai}. ${open === 1 ? 'One needs' : `${open} need`} you.</p></div>
        ${locked ? '<button class="btn press" disabled title="Settle every conflict first">Open the workspace</button>' : '<a class="btn btn-primary press" href="#/ask">Open the workspace</a>'}</div>
      <div style="display:flex;align-items:center;gap:12px"><div class="segs" aria-hidden="true">${V.CONFLICTS.map((_, i) => `<span class="${i < settled ? 'on' : ''}"></span>`).join('')}</div>
        <span style="font-size:13px;font-weight:500;color:var(--v-text-2)" role="status">${settled} of ${V.CONFLICTS.length} settled</span></div>
      ${cards}</main>`;
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
            <span class="small">Archive · ${V.FILES.length} files · ${V.DRAWINGS.length} drawings</span><span class="small">Today, ${hhmm(p.started)}</span></div>
        </section>
        <section class="card hist" aria-label="History"><div class="hist-head"><div style="display:flex;flex-direction:column;gap:4px;min-width:0">
            <span style="font-size:12px;font-weight:500;color:var(--v-muted)">Archive · created today, ${hhmm(p.started)}</span><h2>${esc(V.ARCHIVE)}</h2></div>
            <a class="btn btn-soft press" href="${pr.done ? '#/ask' : '#/ingest'}">Open workspace</a></div>
          <dl class="stats" style="border-bottom:1px solid #f0f1f0">${stat('Files', V.FILES.length)}${stat('Drawings', V.DRAWINGS.length)}${stat('Questions', p.turns.length)}${stat('Signed off', signed)}</dl>
          <h3 style="margin:20px 24px 4px;font-size:15px">History</h3><ol class="events">${events}</ol></section></div></main>`;
  }

  // ---------- events ----------
  const ACTIONS = {
    choose: () => { app.querySelector('[data-files]').click(); return false; },
    sample: () => start(),
    pick: (el) => { const c = V.CONFLICTS.find((x) => x.id === el.dataset.c), i = Number(el.dataset.i);
      S.p.conflicts[c.id] = { mode: 'own', pick: i };
      log(Date.now(), 'cf', `Conflict settled: ${c.title}`, `Your choice · ${V.variantLabels(c)[i]}${c.ai !== null && c.ai !== i ? ', over the AI decision' : ''}`); },
    modify: (el) => { S.p.conflicts[el.dataset.c] = { mode: 'modify', pick: null }; },
    reset: (el) => { const c = V.CONFLICTS.find((x) => x.id === el.dataset.c), was = S.p.conflicts[c.id].mode;
      S.p.conflicts[c.id] = c.ai === null ? { mode: 'open', pick: null } : { mode: 'ai', pick: null };
      if (was === 'own') log(Date.now(), 'cf', c.ai === null ? `Choice undone: ${c.title}` : `AI decision restored: ${c.title}`, c.ai === null ? 'Waiting for you again' : `AI decision approved · ${V.variantLabels(c)[c.ai]}`); },
  };
  function start() { newProject(false); location.hash = '#/ingest'; return false; }

  app.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el || el.getAttribute('aria-disabled') === 'true') return;
    const fn = ACTIONS[el.dataset.act] || window.VAsk.actions[el.dataset.act];
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
  window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
  setInterval(() => { if (!S.p) return; const was = S.p.doneLogged; logDone(); if (was !== S.p.doneLogged && route().name === 'workspaces') render(); else fill(); }, 250);

  window.VApp = { S, render, log, picks, esc, hhmm };
  document.addEventListener('DOMContentLoaded', render);
})();
