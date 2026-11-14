// The project chat (#/chat): a whole new, empty chat over every drawing of the workspace. Nothing is drawn until
// asked; an answer gives one line per drawing (a total only when one drawing answers), each with "Show it on <file>" (the engineer view, #/ask).
(function () {
  'use strict';
  const V = window.VData, T = window.VTriage, esc = window.VPlan.esc;
  const A = () => window.VApp;
  const SUGGEST = V.SUGGEST ? V.SUGGEST.slice(0, 3) : ['How many doors are there?', 'What is the area of the kitchen?', 'How many windows are there?'];
  // After the first answer: follow-ups, each answerable here (data.test.cjs/stoa.test.cjs check the data ones); the
  // elevation question first when the project holds an elevation triage set aside.
  const ELEVATION_Q = 'How many storeys does the building in the elevation have?';
  const FOLLOW = (T.described(ELEVATION_Q, V.FILES) ? [ELEVATION_Q] : [])
    .concat(V.SUGGEST || [...SUGGEST, 'How many rooms are there?', 'What is the net floor area?', 'What is the area of the living room?']);

  // A drawing's value as the person left it: a sign-off wins over the live reading.
  function rowOf(a) {
    const ck = A().S.p.checks[`${a.drawing}:${a.quantity}`];
    if (ck && ck.state === 'checked') return { a, value: ck.value, status: ['ok', `Checked by ${ck.by}`] };
    if (a.key) return { a, value: a.value, status: ['grey', 'Answer key'] };
    return { a, value: a.value, status: a.check ? ['warn', 'Please double-check'] : ['ok', 'Sure'] };
  }

  // An answer from the description of a set-aside drawing (a preview, never Sure): the picture as its reference and
  // what was pulled from it.
  function describedHtml(t, x) {
    const tr = T.of(x.path), d = tr.description, open = A().S.p.chatPic === t.id, file = V.FILES.findIndex((f) => f.path === x.path);
    const from = x.example ? `the description of a set-aside drawing (${T.EXAMPLE})` : 'a model\'s description of a set-aside drawing, not checked by a person';
    const big = open ? `<figure class="chat-big">${T.picture(x.path, `${x.path}, full size`)}${tr.image ? `<a class="small" href="${esc(tr.image)}" target="_blank" rel="noopener">Open the original image</a>` : ''}</figure>` : '';
    return `<article class="turn"><p class="bubble">${esc(t.question)}</p><div class="card chat-card">
      <p class="lead" style="margin:0">${x.matched ? '' : 'The description does not say. What it says: '}“${esc(x.quote)}”</p>
      <p class="chat-pills"><span class="tip" tabindex="0"><span class="pill acc">Preview</span><span role="tooltip" class="tip-body">The real backend keeps this description for later AI use and does not answer from it yet.</span></span>
        <span class="pill grey">Not checked by a person</span></p>
      <p class="small" style="margin:0">From ${esc(from)}. It is not a floor plan, so nothing on it was counted or measured.</p>
      <div class="chat-ref"><span class="label">References</span>
        <button class="chat-thumb press" data-act="chat-pic" data-t="${t.id}" aria-expanded="${open}" aria-label="${open ? 'Close' : 'Open'} the full image of ${esc(x.path)}">${T.picture(x.path, x.path).replace('class="plan tri-pic', 'class="plan thumb tri-pic')}</button>
        <span class="chat-ref-txt"><a class="mono" href="#/file/${file}">${esc(x.path)}</a><span class="small">${esc(T.CLASS_LABEL[T.classOf(x.path)])} · ${esc(T.kindWords(tr.register.kind))}</span>
          ${tr.credit ? `<span class="small credit">Credit: ${esc(tr.credit)}</span>` : ''}</span></div>${big}
      <div class="chat-pulled"><span class="label">What it pulled from the picture</span><dl class="chat-dl">
        <div><dt>Description</dt><dd>${esc(d.text)}</dd></div><div><dt>Kind</dt><dd>${esc(T.kindWords(tr.register.kind))}</dd></div>
        <div><dt>Text printed on it</dt><dd class="tri-text">${d.visible_text ? esc(d.visible_text) : 'None'}</dd></div></dl>
        <details class="tri-more"><summary>Full description</summary><p class="small">${esc(d.detail)}</p></details></div></div></article>`;
  }

  function turnHtml(t) {
    const x = T.described(t.question, V.FILES);
    if (x) return describedHtml(t, x);
    const r = V.askProject(t.question, A().picks());
    const q = `<p class="bubble">${esc(t.question)}</p>`;
    const ok = r.parts.filter((p) => !p.answer.refusal), refused = r.parts.slice(ok.length);
    if (!ok.length) {
      return `<article class="turn">${q}<div class="refusal"><h3 style="margin:0;font-size:17px">I can't answer that from these drawings.</h3>
        <p style="margin:0">${esc(r.parts[0].answer.refusal)}</p><div class="chips-row">${r.canAnswer.map((x) => `<button class="qchip press" data-act="chat-ask" data-q="${esc(x)}">${esc(x)}</button>`).join('')}</div></div></article>`;
    }
    const rows = ok.map((p) => rowOf(p.answer));
    const quantity = ok[0].answer.quantity;
    // a total only when the API gives one (one drawing answered); its value may have been signed off since
    const head = r.total === null
      ? `<p class="lead" style="margin:0">${rows.length} drawings answered. <span class="muted">${esc(r.total_note)}</span></p>`
      : `<p class="lead" style="margin:0"><strong>${esc(V.formatValue(quantity, rows[0].value))}</strong>. <span class="muted">${esc(r.total_note)}</span></p>`;
    const lines = rows.map(({ a, value, status }) => {
      const d = V.drawing(a.drawing);
      return `<li class="chat-row"><span class="chat-line"><span class="mono">${esc(d.name)}</span>: <strong>${esc(V.formatValue(a.quantity, value))}</strong></span>
        <span class="pill ${status[0]}">${esc(status[1])}</span>
        <button class="chat-show press" data-act="show-on" data-d="${d.id}" data-q="${esc(t.question)}">Show it on ${esc(d.name)}</button></li>`;
    }).join('') + refused.map((p) => `<li class="chat-row"><span class="chat-line muted"><span class="mono">${esc(p.name)}</span>: ${esc(p.answer.refusal)}</span></li>`).join('');
    return `<article class="turn">${q}<div class="card" style="padding:20px 22px;display:flex;flex-direction:column;gap:14px">
      ${head}<p class="small" style="margin:0">${esc(V.ruleOf(ok[0].answer))}</p>
      <ul class="chat-rows" aria-label="Per drawing">${lines}</ul></div></article>`;
  }

  function screen() {
    const p = A().S.p;
    const start = !p.chat.length;
    // an empty chat: the bar sits high with suggested questions under it; after the first question it goes to the bottom
    const asked = new Set(p.chat.map((t) => t.question));
    const list = start ? SUGGEST : FOLLOW.filter((x) => !asked.has(x)).slice(0, 3);
    const chip = (x) => `<button class="qchip press" data-act="chat-ask" data-q="${esc(x)}">${esc(x)}</button>`;
    const chips = list.length ? `<div class="chips-row${start ? ' chat-suggest' : ''}" aria-label="${start ? 'Suggested questions' : 'Follow-up questions'}">${list.map(chip).join('')}</div>` : '';
    return `<main class="w820 chat${start ? ' start' : ''}"><h1 class="chat-title">${esc(V.ARCHIVE)}</h1>
      ${start ? '' : `<section aria-label="Chat" class="chat-thread">${p.chat.map(turnHtml).join('')}</section>${chips}`}
      <form class="askbar" data-chat><label class="sr" for="cq">Question</label>
        <input id="cq" name="q" autocomplete="off" placeholder="Ask about the project's drawings" maxlength="200">
        <button class="round press" aria-label="Ask" type="submit"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg></button></form>${start ? chips : ''}</main>`;
  }

  function ask(text) {
    const p = A().S.p, question = text.trim().slice(0, 200);
    if (!question) return false;
    p.chat.push({ id: p.chat.length + 1, question });
    const x = T.described(question, V.FILES);
    if (x) A().log(Date.now(), 'ask', question, `From the description of ${x.path} · a preview, not checked by a person`);
    const r = x ? null : V.askProject(question, A().picks());
    const ok = r ? r.parts.filter((y) => !y.answer.refusal) : [];
    if (r) A().log(Date.now(), 'ask', question, !ok.length ? 'No answer · not in the drawing model'
      : r.total === null ? `${ok.length} drawings answered, not added up · project chat` : `${V.formatValue(ok[0].answer.quantity, r.total)} on one drawing · project chat`);
    requestAnimationFrame(() => { const all = document.querySelectorAll('.turn'); if (all.length) all[all.length - 1].scrollIntoView({ block: 'start', behavior: 'smooth' }); });
    return true;
  }

  const actions = {
    'chat-ask': (el) => { ask(el.dataset.q); },
    'chat-pic': (el) => { const p = A().S.p, id = Number(el.dataset.t); p.chatPic = p.chatPic === id ? null : id; },
    // opens the engineer view on that drawing with the same question asked there, so its marks show
    'show-on': (el) => {
      const p = A().S.p, d = el.dataset.d, question = el.dataset.q;
      p.di = V.DRAWINGS.findIndex((x) => x.id === d);
      p.ov = null;
      const mine = p.turns.filter((t) => t.drawing === d);
      if (!mine.length || mine[mine.length - 1].question !== question) p.turns.push({ id: p.turns.length + 1, drawing: d, question });
      location.hash = '#/ask';
      setTimeout(() => { const all = document.querySelectorAll('.turn'); if (all.length) all[all.length - 1].scrollIntoView({ block: 'start' }); }, 60);
      return false;
    },
  };

  document.addEventListener('submit', (ev) => {
    if (!ev.target.matches('[data-chat]')) return;
    ev.preventDefault();
    if (ask(ev.target.q.value)) A().render();
  });

  window.VChat = { screen, actions };
})();
