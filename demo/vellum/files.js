// The project screen's Drawings and Files lists (ingest.md, under the progress card) and the file trace (#/file/<n>),
// with the triage card of triage.js on a file triage set aside, its call, undo and "Read it as a floor plan".
(function () {
  'use strict';
  const V = window.VData, P = window.VPlan, T = window.VTriage, esc = P.esc;
  const A = () => window.VApp;
  const BADGE = { queued: '… queued', running: '◌ running', ready: '✓ ready', 'set aside': '– set aside' };

  // A file's state now: queued until the reading clock has passed it, then ready (it has a drawing) or set aside; a
  // re-read on a person's call runs queued → running → ready, and keeps "set aside" when it found nothing to read.
  function stateOf(f, i) {
    const pr = A().progress(), ctx = A().ctx();
    const re = T.rapState(f.path, ctx);
    if (re && re !== 'ready') return re;
    if (!pr.done && i >= pr.through) return 'queued';
    return f.drawing ? 'ready' : 'set aside';
  }

  function rowHtml(f, i) {
    const st = stateOf(f, i), ctx = A().ctx();
    let line = f.reason ? `<span class="small">${esc(f.reason)}</span>` : '';
    if (T.of(f.path) && st !== 'queued') {
      const r = T.rowLine(f.path, ctx, !!f.drawing);
      line = `<span class="small">${esc(r.text)}</span>${r.pill ? ` <span class="pill ${r.tone}">${esc(r.pill)}</span>` : ''}${r.by ? `<span class="small"> · ${esc(r.by)}'s call</span>` : ''}`;
    }
    return `<li><a class="file-row press" href="#/file/${i}"><span class="file-main"><span class="mono">${esc(f.path)}</span>${line ? `<span class="file-line">${line}</span>` : ''}</span>
      <span class="file-meta"><span class="pill ${st === 'ready' ? 'ok' : 'grey'}">${BADGE[st]}</span><span class="small">${esc(f.kind)} · ${esc(f.size)}</span></span></a></li>`;
  }

  // Under the progress card: refreshed by the app's clock (no inputs in it).
  function lists() {
    const pr = A().progress(), ctx = A().ctx();
    const ready = V.DRAWINGS.filter((d, i) => pr.done || i < pr.ready);
    const cards = ready.map((d) => `<li class="card dwg-card"><span class="mono" style="font-weight:600">${esc(d.name)}</span>
      <span class="small">${esc(d.meta)} · ${d.lane === 'CAD' ? 'CAD route' : 'vision route'}</span><a class="btn btn-soft press" href="#/ask" data-act="open-drawing" data-d="${d.id}">Open</a></li>`).join('');
    const n = T.notPlans(V.FILES, ctx);
    const tri = pr.done && V.FILES.some((f) => T.of(f.path))
      ? `<p class="small">${esc(T.notPlansLine(n))} <span class="tip" tabindex="0"><span class="pill acc">Preview</span><span role="tooltip" class="tip-body">${T.PREVIEW_TIP}</span></span></p>` : '';
    return `<section aria-label="Drawings"><h2 class="list-h">Drawings</h2>${cards ? `<ul class="dwg-list">${cards}</ul>` : '<p class="muted">No drawing ready yet.</p>'}</section>
      <section aria-label="Files"><h2 class="list-h">Files</h2>${tri}<ul class="file-list card">${V.FILES.map(rowHtml).join('')}</ul></section>`;
  }

  function traceScreen(r) {
    const i = Number(r.n), f = V.FILES[i];
    if (!f) return '<main class="w820"><a class="small" href="#/ingest">Back to the project</a><h1>No such file</h1></main>';
    const st = stateOf(f, i), d = f.drawing && st === 'ready' ? V.drawing(f.drawing) : null;
    const fact = (k, v) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`;
    const facts = fact('File type', f.kind) + fact('Size', f.size) + fact('State', BADGE[st])
      + (d ? fact('Drawing', `${d.name} · ${d.lane === 'CAD' ? 'CAD route' : 'vision route'}`) : fact('Reason', f.reason || (T.of(f.path) ? T.rowLine(f.path, A().ctx(), false).text : '—')));
    const card = T.of(f.path) && (st !== 'queued' || T.rapState(f.path, A().ctx())) ? T.card(f.path, A().ctx(), A().S.signer, A().hhmm) : '';
    return `<main class="w820"><a class="small" href="#/ingest">Back to the project</a>
      <div class="title-row"><div><span class="kicker">${BADGE[st]}</span><h1 class="mono trace-h">${esc(f.path)}</h1></div>
        ${d ? `<a class="btn btn-primary press" href="#/ask" data-act="open-drawing" data-d="${d.id}">Open the drawing</a>` : ''}</div>
      <section class="card"><dl class="stats facts">${facts}</dl></section>${card}</main>`;
  }

  const pathOf = (el) => el.dataset.path;
  const actions = {
    'open-drawing': (el) => { const p = A().S.p; p.di = V.DRAWINGS.findIndex((x) => x.id === el.dataset.d); p.ov = null; return true; },
    'tri-call': (el) => {
      const S = A().S, by = S.signer.trim(), path = pathOf(el);
      if (!by) return false;
      S.p.calls[path] = { verdict: el.dataset.v, by, at: Date.now() };
      A().log(Date.now(), 'tri', `Your call on ${path}`, `${T.VERDICT[el.dataset.v].sentence} · ${by}'s call`);
    },
    'tri-undo': (el) => { const path = pathOf(el); delete A().S.p.calls[path]; A().log(Date.now(), 'tri', `Call undone on ${path}`, 'Back to the rule\'s suggestion'); },
    'tri-read': (el) => {
      const S = A().S, by = S.signer.trim(), path = pathOf(el);
      if (!by || !window.confirm(`Read ${path} as a floor plan? This can't be undone.`)) return false;
      S.p.rap[path] = { by, at: Date.now() };
      A().log(Date.now(), 'tri', `Read as a floor plan: ${path}`, `${by}'s call`);
    },
  };

  // The re-read finishing: called by the app's clock; true when the screen must be drawn again.
  function tick() {
    const p = A().S.p, ctx = A().ctx();
    let changed = false;
    for (const path of Object.keys(p.rap)) {
      if (p.rapDone[path] || T.rapState(path, ctx) !== 'ready') continue;
      p.rapDone[path] = true;
      const d = V.readAsPlan(path);
      A().log(Date.now(), 'tri', d ? `Drawing ready: ${d.name}` : `Read as a floor plan: ${path}`, d ? 'Read as a floor plan on a person\'s call' : 'No rooms or openings were found on it');
      changed = true;
    }
    return changed;
  }

  // the one typed name of the session (also the double-check sign-off's)
  document.addEventListener('input', (ev) => {
    if (!ev.target.matches('[data-name]')) return;
    A().S.signer = ev.target.value;
    for (const b of document.querySelectorAll('[data-needs-name]')) b.disabled = !ev.target.value.trim();
  });

  window.VFiles = { lists, traceScreen, actions, tick };
})();
