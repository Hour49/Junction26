// Screen 4: ask about a drawing, get the number with its marks, its references and, below the certificate, a
// double-check (Looks right / Fix it, then a sign-off with a typed name).
(function () {
  'use strict';
  const V = window.VData, P = window.VPlan, esc = P.esc;
  const A = () => window.VApp;
  const ROLE = { read: 'Read: the value comes from this file', shown: 'Shown: the rendering the marks are drawn on',
    second: 'Checked: an independent second count', source: 'Asked about: the answer key\'s question is on this file',
    same: 'The same floor in another format' };
  const SUGGEST = ['How many doors are on this floor?', 'How many windows?', 'What is the net floor area?', 'How many rooms?',
    'What fire rating do the stair doors need?'];
  const KEY_TIP = 'Answer key: the value the Stoa dataset gives for this question. Vellum did not read it from the drawing here.';
  const SURE_TIP = 'Sure: exact CAD geometry and nothing in dispute, so the answer is certified and no person needs to check it.';

  const cur = () => V.DRAWINGS[A().S.p.di];
  const keyOf = (t) => `${t.drawing}:${V.parseQuestion(t.question)}`;
  function checkOf(t) {
    const p = A().S.p, key = keyOf(t);
    if (!p.checks[key]) p.checks[key] = { state: 'needs', rejected: new Set(), added: new Set() };
    return p.checks[key];
  }
  const nounOf = (q, n) => (q === 'area' || q === 'room' ? (n === 1 ? 'room' : 'rooms') : V.noun(q, n));

  function screen() {
    const p = A().S.p, d = cur(), turns = p.turns.filter((t) => t.drawing === d.id);
    const n = V.DRAWINGS.length;
    const bar = `<div class="dwg-bar"><div><span class="mono" style="font-size:14px;font-weight:600">${esc(d.name)}</span>
        <span class="small">${esc(d.meta)} · <span aria-live="polite">${p.di + 1} / ${n}</span></span></div>
      <button class="round press" data-act="drawing" data-d="-1" aria-label="Previous drawing"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1d1d1f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
      <button class="round press" data-act="drawing" data-d="1" aria-label="Next drawing"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1d1d1f" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button></div>`;
    const empty = turns.length ? '' : `<section class="card"><div style="padding:20px;background:#fafafc">${P.plain(d, 'clean')}</div>
      <p style="margin:0;padding:16px 22px 20px">${d.image ? 'Ask about this floor: its answer key holds counts and net floor areas.' : 'Ask about this drawing: doors, windows, rooms or the net floor area. Every answer points at the places it counted.'}</p></section>`;
    return `<main class="w1040 ask">${bar}${empty}${turns.map(turnHtml).join('')}
      <div class="chips-row" aria-label="Suggested questions">${(V.SUGGEST || SUGGEST).map((q) => `<button class="qchip press" data-act="ask" data-q="${esc(q)}">${esc(q)}</button>`).join('')}</div>
      <form class="askbar" data-ask><label class="sr" for="q">Ask about ${esc(d.name)}</label>
        <input id="q" name="q" autocomplete="off" placeholder="Ask about ${esc(d.name)}" maxlength="200">
        <button class="round press" aria-label="Ask" type="submit"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg></button></form></main>`;
  }

  function turnHtml(t) {
    const d = V.drawing(t.drawing), a = V.answer(d.id, t.question, A().picks());
    const q = `<p class="bubble">${esc(t.question)}</p>`;
    if (a.refusal) {
      const near = (a.near || []).slice(0, 4).map((x) => `<button class="qchip press" data-act="ask" data-q="${esc(x)}">${esc(x)}</button>`).join('');
      return `<article class="turn">${q}<div class="refusal"><span><span class="pill grey">No answer</span></span><p style="margin:0">${esc(a.refusal)}</p>${near ? `<div class="chips-row">${near}</div>` : ''}</div></article>`;
    }
    const ck = a.check ? checkOf(t) : null;
    const edits = ck && (ck.state === 'fixing' || ck.state === 'confirm') ? ck : null;
    const value = a.key ? a.value : ck && ck.state === 'checked' ? ck.value : V.valueOf(a.marks, a.quantity, edits);
    const shown = V.formatValue(a.quantity, value);
    const lead = a.quantity === 'area' ? `The net floor area is <strong>${shown}</strong>.` : `There ${value === 1 ? 'is' : 'are'} <strong>${shown}</strong> on this drawing.`;
    const flagged = new Map(ck && ck.state !== 'checked' ? a.check.disputed.map((x) => [x.mark_id || x.place, x.why]) : []);
    const fixing = !!ck && ck.state === 'fixing';
    const ov = A().S.p.ov && A().S.p.ov.turn === t.id ? A().S.p.ov.file : null;
    const files = V.FILES.filter((f) => f.drawing === d.id);
    const sheet = ov === null ? '' : (() => {
      const f = files[ov], look = P.lookOfFile(f.kind);
      const bg = { cad: '#16181d', pdf: '#ffffff', raster: '#f1f0ec', scan: '#f3eedd' }[look];
      return `<div class="sheet" role="dialog" aria-label="Original file: ${esc(f.path)}" style="background:${bg}"><div class="sheet-bar"><span class="num">${ov + 1}</span>
        <span><span class="mono" style="font-size:13px;font-weight:600">${esc(f.path)}</span><span class="muted">${esc(ROLE[f.role])}</span></span>
        <button class="x press" data-act="close-ov" aria-label="Close the original"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1d1d1f" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
        <div class="sheet-body">${P.original(d, f, a)}</div></div>`;
    })();
    const legend = a.marks.length ? [`<span><i class="lg" aria-hidden="true"></i>counted</span>`] : [];
    if (a.marks.some((m) => m.excluded)) legend.push('<span><i class="lg dash" aria-hidden="true"></i>open doorway, left out by the rule</span>');
    if (flagged.size) legend.push('<span><i class="lg warn" aria-hidden="true"></i>not sure, please look</span>');
    // in Stoa mode only the image file can be opened; the PDF and DXF are listed, not shipped
    const refs = files.map((f, i) => {
      const body = `<span class="num">${i + 1}</span><span><span class="mono" style="font-weight:600">${esc(f.path)}</span><span class="muted">${esc(ROLE[f.role])}</span></span>`;
      return d.image && !f.image ? `<li><span class="ref">${body}</span></li>`
        : `<li><button class="ref press" data-act="ref" data-t="${t.id}" data-f="${i}" aria-pressed="${ov === i}">${body}</button></li>`;
    }).join('');
    const status = a.key ? `<span class="tip" tabindex="0"><span class="pill grey">Answer key</span><span role="tooltip" class="tip-body">${KEY_TIP}</span></span>`
      : !a.check ? `<span class="tip" tabindex="0"><span class="pill ok">Sure</span><span role="tooltip" class="tip-body">${SURE_TIP}</span></span>` : '';
    return `<article class="turn">${q}<p class="lead">${lead} <span class="muted">${esc(V.ruleOf(a))}</span></p>
      <div class="card"><div class="answer">
        <figure aria-label="Drawing"><span style="display:flex;flex-direction:column"><span class="mono" style="font-size:14px;font-weight:600">${esc(d.name)}</span><span class="small">${esc(d.meta)}</span></span>
          <div class="plan-box">${P.answerPlan(d, a, { flagged, rejected: edits ? edits.rejected : null, added: edits ? edits.added : null, fixing, turn: t.id })}${sheet}</div>
          <figcaption class="legend">${legend.join('')}</figcaption>${d.credit || V.CREDIT ? `<p class="small credit">Credit: ${esc((d.credit || V.CREDIT).replace(/^All files:\s*/, ''))}</p>` : ''}</figure>
        <div class="side">
          <div class="value"><b>${V.formatValue(a.quantity, value).split(' ')[0]}</b><span>${a.quantity === 'area' ? 'm² net' : nounOf(a.quantity, value)}</span>${status}</div>
          ${a.check ? checkHtml(t, a, ck, value) : a.key ? '' : '<p class="small">Certified: exact geometry and nothing in dispute. No person needs to check this.</p>'}
          <div style="display:flex;flex-direction:column;gap:4px"><span class="label">How it was found</span><p class="small">${methodLine(d, a)}</p></div>
          <div style="display:flex;flex-direction:column;gap:8px"><span class="label">References</span><ol class="refs">${refs}</ol></div>
        </div></div></div></article>`;
  }

  function methodLine(d, a) {
    if (a.key) return `From the dataset's answer key: “${esc(a.keyQuestion)}” The data has no positions, so there are no marks.`;
    const pk = A().picks();
    const c = V.CONFLICTS.find((x) => x.drawing === d.id && x.variants.some((v) => v.kind === a.quantity));
    if (c && pk[c.id] === null) return 'A conflict on this drawing is open: <a href="#/conflicts">settle it in Conflicts</a>.';
    if (c) return `${esc(c.title)}: settled in Conflicts (${A().S.p.conflicts[c.id].mode === 'own' ? 'your choice' : 'AI decision approved'}).`;
    const second = V.FILES.find((f) => f.drawing === d.id && f.role === 'second');
    if (second) return `Read from the geometry, then checked against <span class="mono">${esc(second.path)}</span>, an independent second reading: the same value.`;
    return `${d.lane === 'CAD' ? 'Read from the geometry' : 'Read from the image by vision'}; measured by one method, no second check.`;
  }

  function checkHtml(t, a, ck, value) {
    if (ck.state === 'checked') {
      return `<div class="dc checked"><span><span class="pill ok on-surface">Checked by a person</span></span>
        <h3>Checked by ${esc(ck.by)}, today ${A().hhmm(ck.at)}</h3><p>Signed off at ${esc(V.formatValue(a.quantity, ck.value))}.</p></div>`;
    }
    const dis = a.check.disputed, noun = nounOf(a.quantity, 2);
    if (ck.state === 'confirm') {
      return `<div class="dc"><span><span class="pill warn on-surface">Please double-check</span></span>
        <label class="signas">Sign off ${esc(V.formatValue(a.quantity, value))} as
          <input data-signer value="${esc(A().S.signer)}" placeholder="Your name" maxlength="60" autocomplete="name"></label>
        <div class="dc-btns"><button class="btn btn-primary press" data-act="confirm" data-t="${t.id}"${A().S.signer.trim() ? '' : ' disabled'}>Confirm</button>
          <button class="btn btn-plain press" data-act="back" data-t="${t.id}">Back</button></div></div>`;
    }
    const fixing = ck.state === 'fixing';
    const rows = dis.map((x) => {
      const m = a.marks.find((k) => k.id === (x.mark_id || x.place));
      const label = x.mark_id === null ? '+' : m && m.n ? m.n : '?';
      const who = Object.entries(x.readers).map(([r, s]) => `${r}: ${s}`).join(' · ');
      let act = '';
      if (x.mark_id === null) {
        const on = ck.added.has(x.place);
        act = `<button class="btn ${on ? 'btn-plain' : 'btn-soft'} press" data-act="add" data-t="${t.id}" data-mark="${x.place}">${on ? 'Remove' : 'Add it here'}</button>`;
      } else if (fixing && m && m.counted) {
        const out = ck.rejected.has(m.id);
        act = `<button class="btn btn-plain press" data-act="toggle-mark" data-t="${t.id}" data-mark="${m.id}">${out ? 'Restore' : 'Reject'}</button>`;
      }
      return `<li data-hot="${x.mark_id || x.place}"><span class="dis-n" aria-hidden="true">${label}</span><span style="display:flex;flex-direction:column;gap:2px;min-width:0">
        <span class="dis-why">${esc(x.why)}</span><span class="dis-who">${esc(who)}</span></span>${act ? `<span class="dis-act">${act}</span>` : ''}</li>`;
    }).join('');
    const head = fixing
      ? `<span><span class="pill acc">Fixing</span></span><h3>Click a mark on the plan to reject or restore it.</h3><p>The value updates as you go.</p>`
      : `<span><span class="pill warn on-surface">Please double-check</span></span><h3>${dis.length ? `Please double-check: we're not sure about ${dis.length} of these ${noun}.` : 'Please double-check this value.'}</h3><p>${esc(a.check.reason)}</p>`;
    const btns = fixing
      ? `<button class="btn btn-primary press" data-act="done-fix" data-t="${t.id}">Done fixing</button><button class="btn btn-plain press" data-act="cancel-fix" data-t="${t.id}">Cancel</button>`
      : `<button class="btn btn-primary press" data-act="looks-right" data-t="${t.id}">Looks right</button><button class="btn btn-plain press" data-act="fix" data-t="${t.id}">Fix it</button>`;
    return `<div class="dc">${head}${rows ? `<ul class="dis" aria-label="Places in question">${rows}</ul>` : ''}<div class="dc-btns">${btns}</div></div>`;
  }

  // ---------- actions ----------
  const turnOf = (el) => A().S.p.turns.find((t) => t.id === Number(el.dataset.t));
  function ask(text) {
    const p = A().S.p, d = cur(), question = text.trim().slice(0, 200);
    if (!question) return false;
    const t = { id: p.turns.length + 1, drawing: d.id, question };
    p.turns.push(t);
    const a = V.answer(d.id, question, A().picks());
    A().log(Date.now(), 'ask', question, a.refusal ? `No answer · ${d.name} · not in the drawing model`
      : `${V.formatValue(a.quantity, a.value)} · ${d.name} · ${a.check ? 'asked for a double-check' : 'sure'}`);
    return true;
  }
  function sign(t) {
    const S = A().S, ck = checkOf(t), a = V.answer(t.drawing, t.question, A().picks());
    Object.assign(ck, { state: 'checked', by: S.signer.trim(), at: Date.now(), value: V.valueOf(a.marks, a.quantity, ck) });
    A().log(ck.at, 'sign', `Signed off: ${t.question}`, `${V.formatValue(a.quantity, ck.value)} · ${V.drawing(t.drawing).name} · checked by ${ck.by}`);
  }
  function scrollToLast() { requestAnimationFrame(() => { const all = document.querySelectorAll('.turn'); if (all.length) all[all.length - 1].scrollIntoView({ block: 'start', behavior: 'smooth' }); }); }

  const actions = {
    drawing: (el) => { const p = A().S.p, n = V.DRAWINGS.length; p.di = (p.di + Number(el.dataset.d) + n) % n; p.ov = null; },
    ask: (el) => { if (ask(el.dataset.q)) scrollToLast(); },
    ref: (el) => { const p = A().S.p, t = Number(el.dataset.t), f = Number(el.dataset.f);
      p.ov = p.ov && p.ov.turn === t && p.ov.file === f ? null : { turn: t, file: f }; },
    'close-ov': () => { A().S.p.ov = null; },
    'looks-right': (el) => { checkOf(turnOf(el)).state = 'confirm'; },
    fix: (el) => { checkOf(turnOf(el)).state = 'fixing'; },
    'done-fix': (el) => { checkOf(turnOf(el)).state = 'confirm'; },
    'cancel-fix': (el) => { Object.assign(checkOf(turnOf(el)), { state: 'needs', rejected: new Set(), added: new Set() }); },
    back: (el) => { const ck = checkOf(turnOf(el)); ck.state = ck.rejected.size || ck.added.size ? 'fixing' : 'needs'; },
    confirm: (el) => { if (A().S.signer.trim()) sign(turnOf(el)); },
    add: (el) => { const ck = checkOf(turnOf(el)), id = el.dataset.mark;
      if (ck.state === 'needs') ck.state = 'fixing';
      if (ck.added.has(id)) ck.added.delete(id); else ck.added.add(id); },
    'toggle-mark': (el) => {
      const t = turnOf(el), ck = checkOf(t), id = el.dataset.mark, a = V.answer(t.drawing, t.question, A().picks()), m = a.marks.find((x) => x.id === id);
      if (m && m.missed) { if (ck.added.has(id)) ck.added.delete(id); else ck.added.add(id); return; }
      if (ck.rejected.has(id)) ck.rejected.delete(id); else ck.rejected.add(id);
    },
  };

  document.addEventListener('submit', (ev) => {
    if (!ev.target.matches('[data-ask]')) return;
    ev.preventDefault();
    if (ask(ev.target.q.value)) { A().render(); scrollToLast(); }
  });
  document.addEventListener('input', (ev) => {
    if (!ev.target.matches('[data-signer]')) return;
    A().S.signer = ev.target.value;
    const btn = ev.target.closest('.dc').querySelector('[data-act="confirm"]');
    btn.disabled = !ev.target.value.trim();
  });
  // hovering a place in question rings its mark on the plan
  const hot = (ev, on) => {
    const li = ev.target.closest && ev.target.closest('[data-hot]');
    if (!li) return;
    li.classList.toggle('hot', on);
    const g = li.closest('.answer').querySelector(`.mark[data-id="${CSS.escape(li.dataset.hot)}"]`);
    if (g) g.classList.toggle('hot', on);
  };
  document.addEventListener('mouseover', (ev) => hot(ev, true));
  document.addEventListener('mouseout', (ev) => hot(ev, false));

  window.VAsk = { screen, actions };
})();
