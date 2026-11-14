// The project chat (#/chat): a whole new, empty chat over every drawing of the workspace. Nothing is drawn until
// asked; an answer gives one line per drawing (a total only when one drawing answers), each with "Show it on <file>" (the engineer view, #/ask).
(function () {
  'use strict';
  const V = window.VData, esc = window.VPlan.esc;
  const A = () => window.VApp;
  const SUGGEST = ['How many doors are there?', 'What is the area of the kitchen?', 'How many windows are there?'];

  // A drawing's value as the person left it: a sign-off wins over the live reading.
  function rowOf(a) {
    const ck = A().S.p.checks[`${a.drawing}:${a.quantity}`];
    if (ck && ck.state === 'checked') return { a, value: ck.value, status: ['ok', `Checked by ${ck.by}`] };
    return { a, value: a.value, status: a.check ? ['warn', 'Please double-check'] : ['ok', 'Sure'] };
  }

  function turnHtml(t) {
    const r = V.askProject(t.question, A().picks());
    const q = `<p class="bubble">${esc(t.question)}</p>`;
    if (r.refusal) {
      return `<article class="turn">${q}<div class="refusal"><h3 style="margin:0;font-size:17px">I can't answer that from these drawings.</h3>
        <p style="margin:0">${esc(r.refusal)}</p><div class="chips-row">${r.canAnswer.map((x) => `<button class="qchip press" data-act="chat-ask" data-q="${esc(x)}">${esc(x)}</button>`).join('')}</div></div></article>`;
    }
    const rows = r.rows.map(rowOf);
    // a total only when one drawing answers (r.total set); its value may have been signed off since
    const head = r.total === null
      ? `<p class="lead" style="margin:0">${rows.length} drawings answered. <span class="muted">${esc(r.total_note)}</span></p>`
      : `<p class="lead" style="margin:0"><strong>${esc(V.formatValue(r.quantity, rows[0].value))}</strong> on the one drawing that answered.</p>`;
    const lines = rows.map(({ a, value, status }) => {
      const d = V.drawing(a.drawing);
      return `<li class="chat-row"><span class="chat-line"><span class="mono">${esc(d.name)}</span>: <strong>${esc(V.formatValue(a.quantity, value))}</strong></span>
        <span class="pill ${status[0]}">${esc(status[1])}</span>
        <button class="chat-show press" data-act="show-on" data-d="${d.id}" data-q="${esc(t.question)}">Show it on ${esc(d.name)}</button></li>`;
    }).join('');
    return `<article class="turn">${q}<div class="card" style="padding:20px 22px;display:flex;flex-direction:column;gap:14px">
      ${head}<p class="small" style="margin:0">${esc(V.ruleOf(r.rows[0]))}</p>
      <ul class="chat-rows" aria-label="Per drawing">${lines}</ul></div></article>`;
  }

  function screen() {
    const p = A().S.p;
    const start = !p.chat.length;
    // an empty chat: the bar sits high with suggested questions under it; after the first question it goes to the bottom
    const chips = start ? `<div class="chips-row chat-suggest" aria-label="Suggested questions">${SUGGEST.map((x) => `<button class="qchip press" data-act="chat-ask" data-q="${esc(x)}">${esc(x)}</button>`).join('')}</div>` : '';
    return `<main class="w820 chat${start ? ' start' : ''}"><h1 class="chat-title">${esc(V.ARCHIVE)}</h1>
      ${start ? '' : `<section aria-label="Chat" class="chat-thread">${p.chat.map(turnHtml).join('')}</section>`}
      <form class="askbar" data-chat><label class="sr" for="cq">Question</label>
        <input id="cq" name="q" autocomplete="off" placeholder="Ask about the project's drawings" maxlength="200">
        <button class="round press" aria-label="Ask" type="submit"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg></button></form>${chips}</main>`;
  }

  function ask(text) {
    const p = A().S.p, question = text.trim().slice(0, 200);
    if (!question) return false;
    p.chat.push({ id: p.chat.length + 1, question });
    const r = V.askProject(question, A().picks());
    A().log(Date.now(), 'ask', question, r.refusal ? 'No answer · not in the drawing model'
      : r.total === null ? `${r.rows.length} drawings answered, not added up · project chat` : `${V.formatValue(r.quantity, r.total)} on one drawing · project chat`);
    requestAnimationFrame(() => { const all = document.querySelectorAll('.turn'); if (all.length) all[all.length - 1].scrollIntoView({ block: 'start', behavior: 'smooth' }); });
    return true;
  }

  const actions = {
    'chat-ask': (el) => { ask(el.dataset.q); },
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
