// The project's issues list (#155, decision 0008), derived from the data and the clicks: conflicts, files set aside
// for their format, and files triage set aside as not floor plans (unrelated_file). Pure part testable under node.
(function (root) {
  'use strict';
  const SEVERITY = [['fails_rule', 'Fails a rule'], ['needs_person', 'Needs a person'], ['note', 'Note']];
  const KIND = { conflict: ['Conflict', '⇄'], set_aside: ['Set aside', '–'], unrelated_file: ['Not a floor plan', '▭'] };
  const STATE = { open: ['open', '●'], settled: ['settled', '✓'] };
  const CSV_COLUMNS = ['id', 'kind', 'severity', 'state', 'file', 'file_id', 'drawing_id', 'floor', 'page', 'x0', 'y0', 'x1', 'y1',
    'mark_id', 'why', 'quantity', 'question', 'reason', 'check'];

  // ctx: { done, conflicts {id: {mode}}, calls, rap, now } (triage.js's ctx plus the conflict modes)
  function issuesOf(V, T, ctx) {
    if (!ctx.done) return [];
    const out = [];
    for (const c of V.CONFLICTS) {
      const mode = ctx.conflicts[c.id].mode, settled = mode === 'ai' || mode === 'own';
      const d = V.drawing(c.drawing), file = (V.FILES.find((f) => f.drawing === d.id && f.role === 'read') || V.FILES.find((f) => f.drawing === d.id)).path;
      out.push({ id: `conflict-${c.id}`, kind: 'conflict', severity: settled ? 'note' : 'needs_person', state: settled ? 'settled' : 'open',
        file, file_id: V.FILES.findIndex((f) => f.path === file), drawing_id: d.id, order: V.DRAWINGS.indexOf(d), reason: null,
        why: `${c.title}${/[.?!]$/.test(c.title) ? '' : '.'} ${settled ? (mode === 'own' ? 'Settled by a person\'s choice.' : 'Settled by the AI.') : 'The rules could not decide, so it needs a person.'}` });
    }
    V.FILES.forEach((f, i) => {
      const base = { file: f.path, file_id: i, drawing_id: null, order: V.DRAWINGS.length + i };
      const tri = T.issueOf(f.path, ctx);
      if (tri) out.push({ id: `file-${i}`, kind: 'unrelated_file', ...base, ...tri });
      else if (!f.drawing && !T.of(f.path)) out.push({ id: `file-${i}`, kind: 'set_aside', severity: 'note', state: 'open', ...base, reason: f.reason, why: `Set aside at ingest: ${f.reason}.` });
    });
    const rank = (s) => SEVERITY.findIndex(([k]) => k === s);
    return out.sort((a, b) => rank(a.severity) - rank(b.severity) || a.order - b.order).map((x, i) => ({ ...x, n: i + 1 }));
  }

  function countsLine(list) {
    const n = (s) => list.filter((x) => x.state === s).length;
    return [[n('open'), 'open'], [n('settled'), 'settled']].filter(([k]) => k).map(([k, w]) => `${k} ${w}`).join(' · ');
  }

  const cell = (v) => (v === null || v === undefined ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  function csv(list) {
    return [CSV_COLUMNS.join(',')].concat(list.map((x) => CSV_COLUMNS.map((k) => cell(x[k])).join(','))).join('\n') + '\n';
  }

  const API = { SEVERITY, KIND, STATE, CSV_COLUMNS, issuesOf, countsLine, csv };
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; return; }

  // ---------- the screen (browser only) ----------
  const A = () => root.VApp, V = root.VData, T = root.VTriage, esc = root.VPlan.esc;
  const list = () => issuesOf(V, T, A().ctx());

  function jump(x) {
    if (x.kind === 'conflict') return [x.state === 'open' ? 'Settle' : 'See the conflict', '#/conflicts'];
    if (x.kind === 'set_aside') return ['Why it was set aside', `#/file/${x.file_id}`];
    return [x.state === 'open' ? 'Make a call' : 'See the call', `#/file/${x.file_id}`];
  }

  function screen() {
    const all = list(), f = A().S.p.issueFilter;
    if (!A().ctx().done) return '<main class="w820"><h1>Issues</h1><p class="muted">The issues list is ready once the project is read.</p><a class="btn btn-soft press" href="#/ingest">See the reading</a></main>';
    const shown = all.filter((x) => (!f.kind || x.kind === f.kind) && (!f.state || x.state === f.state));
    const opts = (key, words) => {
      const present = [...new Set(all.map((x) => x[key]))];
      return `<option value="">All</option>${present.map((k) => `<option value="${k}"${f[key] === k ? ' selected' : ''}>${esc(words[k][0])} (${all.filter((x) => x[key] === k).length})</option>`).join('')}`;
    };
    const groups = SEVERITY.map(([sev, head]) => {
      const rows = shown.filter((x) => x.severity === sev);
      if (!rows.length) return '';
      return `<section class="iss-group" aria-label="${head}"><h2>${head}</h2><ol class="iss">${rows.map((x) => {
        const [label, href] = jump(x);
        return `<li class="card iss-row"><span class="iss-n" aria-hidden="true">${x.n}</span><div class="iss-body">
          <div class="iss-top"><span class="pill grey">${KIND[x.kind][1]} ${KIND[x.kind][0]}</span><span class="small">${STATE[x.state][1]} ${STATE[x.state][0]}</span></div>
          <p class="iss-why">${esc(x.why)}</p><p class="small mono">${esc(x.file)} · ${x.drawing_id ? 'the whole drawing' : 'not on a drawing'}</p></div>
          <a class="btn btn-soft press iss-go" href="${href}">${label}</a></li>`;
      }).join('')}</ol></section>`;
    }).join('');
    return `<main class="w820"><div class="title-row"><div><span class="kicker ok">${esc(V.ARCHIVE)}</span><h1>Issues</h1>
        <p class="muted" style="margin:0">${all.length ? esc(countsLine(all)) : ''}</p></div>
        ${all.length ? '<button class="btn btn-soft press" data-act="iss-csv">Export CSV</button>' : ''}</div>
      ${all.length ? `<div class="iss-filters"><label class="small">Kind <select data-filter="kind">${opts('kind', KIND)}</select></label>
        <label class="small">State <select data-filter="state">${opts('state', STATE)}</select></label></div>` : ''}
      ${all.length ? groups || '<p class="muted">No issue matches these filters.</p>' : '<p class="muted">No issues: nothing needs a look.</p>'}</main>`;
  }

  const actions = {
    'iss-csv': () => {
      const url = URL.createObjectURL(new Blob([csv(list())], { type: 'text/csv;charset=utf-8' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: `${V.ARCHIVE.replace(/\.zip$/, '')}-issues.csv` });
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      return false;
    },
  };
  document.addEventListener('change', (ev) => {
    const k = ev.target.dataset && ev.target.dataset.filter;
    if (!k || !A().S.p) return;
    A().S.p.issueFilter[k] = ev.target.value || null;
    A().render();
  });

  root.VIssues = { screen, actions };
})(typeof window !== 'undefined' ? window : globalThis);
