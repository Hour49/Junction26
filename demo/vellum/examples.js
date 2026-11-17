// Examples (#/example/<id>): answers the full app gave during the event, on three drawings we may publish. Every
// question, value, confidence text, reason and mark place below is copied from the app's recorded chats (the live
// app's project store, env 8ed526b, 15 Nov 2026: projects b2413df093d2 chat 43965f59a478, a5d889c6c3dd chat
// 0164b575c1ac turn 3, 64897def642b chat 5b89b02a86fd); only the "[1]" references are taken out of the chat's text.
// Marks are [x0, y0, x1, y1] as fractions of the page; a disputed place's mark is the number of the mark it is on, or
// null for a place the answer did not count. The pictures in examples/ are web copies of the files the app read.
// Plain script (global VExamples) and node-loadable.
(function (root) {
  'use strict';

  const EXAMPLES = [
    { id: 'scan', title: 'A scan from 1973', name: 'Isaac Franklin House, first floor plan',
      blurb: 'A scanned survey sheet: the doors are read from its pixels, and the places the readers disagree on are marked.',
      credit: ['Plan: Isaac Franklin House, White Pine, Tennessee, sheet 2 of 6 of survey HABS TN-197 (1973). Historic American Buildings Survey, National Park Service; Library of Congress, Prints and Photographs Division. Public domain.', 'https://www.loc.gov/pictures/item/tn0085.sheet.00002a/'],
      images: { franklin: { src: 'franklin.webp', w: 3000, h: 2370, kind: 'JPG scan' } } },
    { id: 'flat', title: 'A drawn PDF', name: 'Our sample flat',
      blurb: 'A flat we drew by code as a vector PDF: the doors are read from its lines, so the answer is High.',
      credit: ['Plan: our own sample flat, drawn by code (tools/readme-media/make_plan.py), MIT licence.', 'https://github.com/Hour49/Junction26/blob/main/tools/readme-media/make_plan.py'],
      images: { flat: { src: 'flat.webp', w: 440, h: 350, kind: 'Vector PDF' } } },
    { id: 'heat', title: 'Heating sheets and their model', name: 'DigitalHub office building, heating',
      blurb: 'Two heating sheets and the heating model (IFC) of one office building: the radiators counted on each, side by side.',
      credit: ['Sheets rendered by team Hour49 from the DigitalHub v2 models, © 2020 RWTH Aachen University, E3D Institute of Energy Efficiency and Sustainable Building, MIT licence.', 'https://github.com/RWTH-E3D/DigitalHub'],
      images: { h101: { src: 'h101.webp', w: 3220, h: 959, kind: 'PNG sheet' }, h102: { src: 'h102.webp', w: 3220, h: 959, kind: 'PNG sheet' } } },
  ];
  const TURNS = {
   "scan": [
    {
     "q": "How many toilets are there?",
     "text": "There is 1 toilet.",
     "model": "gemini-4-hydrogen",
     "cost_usd": 0.015192,
     "parts": [
      {
       "file": "franklin-sheet2-3000.jpg",
       "level": "high",
       "level_text": "High confidence: checked by Carbon: two readers agree. Gemini Carbon, read as a second reader, counted the same here. On our validation plans, 95% of the answers checked this way were exact (536 of 563).",
       "route": "raster",
       "value": 1,
       "noun": "toilet",
       "rule": "every element, room and plan the drawing lists counts once",
       "scale": "3/16\"= 1'-0\", printed scale bar (one bar)",
       "image": "franklin",
       "marks": [[0.388, 0.4721, 0.3989, 0.4928]]
      }
     ]
    },
    {
     "q": "And how many doors?",
     "text": "There are 19 doors, though the confidence is low and the readers disagree at 3 places.",
     "model": "gemini-4-hydrogen",
     "cost_usd": 0.013569,
     "parts": [
      {
       "file": "franklin-sheet2-3000.jpg",
       "level": "low",
       "level_text": "Low confidence: on our validation plans, 59% of the answers rated this way were exact (405 of 691). Check it before you use it.",
       "route": "raster",
       "value": 19,
       "noun": "doors",
       "rule": "every element, room and plan the drawing lists counts once",
       "scale": "3/16\"= 1'-0\", printed scale bar (one bar)",
       "image": "franklin",
       "marks": [[0.2294, 0.1815, 0.2537, 0.1941], [0.5255, 0.3405, 0.5351, 0.3729], [0.4302, 0.5492, 0.4515, 0.5586], [0.6264, 0.6365, 0.6354, 0.6692], [0.405, 0.2795, 0.4308, 0.2914], [0.627, 0.3405, 0.6365, 0.3725], [0.699, 0.4631, 0.7231, 0.4724], [0.699, 0.5494, 0.7232, 0.5582], [0.3755, 0.3042, 0.3838, 0.3354], [0.3338, 0.2808, 0.3423, 0.3121], [0.5642, 0.7301, 0.5948, 0.7417], [0.5667, 0.2795, 0.5956, 0.2908], [0.3746, 0.5877, 0.3843, 0.6186], [0.5246, 0.6368, 0.5344, 0.6697], [0.3458, 0.276, 0.3693, 0.2808], [0.3471, 0.354, 0.3707, 0.3595], [0.7807, 0.4947, 0.7882, 0.5264], [0.474, 0.5009, 0.4769, 0.521], [0.4739, 0.5254, 0.4773, 0.5453]],
       "check": {
        "reason": "Please double-check the doors: the readers disagree at 3 places, marked on the drawing.",
        "disputed": [
         {
          "mark": 19,
          "box": [0.4739, 0.5254, 0.4773, 0.5453],
          "why": "Counted as a door, but 1 of the 2 other readers sees nothing here.",
          "readers": {
           "answer": "door, score 0.45, 8 of 8 views",
           "l1": "door, score 0.66",
           "m1": "nothing"
          }
         },
         {
          "mark": null,
          "box": [0.4741, 0.4737, 0.4768, 0.4954],
          "why": "Not counted, but 1 of the 2 other readers sees a door here.",
          "readers": {
           "answer": "nothing",
           "l1": "door, score 0.46",
           "m1": "nothing"
          }
         },
         {
          "mark": 14,
          "box": [0.5246, 0.6368, 0.5344, 0.6697],
          "why": "Counted as a door, but 1 of the 2 other readers sees nothing here.",
          "readers": {
           "answer": "door, score 0.68, 8 of 8 views",
           "l1": "door, score 0.41",
           "m1": "nothing"
          }
         }
        ]
       }
      }
     ]
    }
   ],
   "flat": [
    {
     "q": "How many doors are there?",
     "text": "There are 8 doors.",
     "model": "gemini-4-hydrogen",
     "cost_usd": 0.020234,
     "parts": [
      {
       "file": "flat.pdf",
       "level": "high",
       "level_text": "High confidence: on our reference drawings of this kind, 794 of 794 answers were exact.",
       "route": "vector",
       "value": 8,
       "noun": "doors",
       "rule": "every element, room and plan the drawing lists counts once",
       "scale": "1:100, sheet text 1:100; no scale bar found",
       "image": "flat",
       "marks": [[0.2906, 0.4154, 0.3486, 0.4365], [0.3872, 0.4154, 0.4452, 0.4365], [0.6449, 0.4154, 0.7094, 0.4365], [0.2262, 0.5304, 0.2777, 0.5515], [0.326, 0.5304, 0.3776, 0.5515], [0.4517, 0.5304, 0.5097, 0.5515], [0.5934, 0.7393, 0.6514, 0.771], [0.1089, 0.443, 0.1341, 0.524]]
      }
     ]
    }
   ],
   "heat": [
    {
     "q": "Do the heating sheets and the heating model agree on the number of radiators on each floor?",
     "text": "Yes, the heating sheets and the heating model agree: there are 29 radiators on the ground floor (E00) and 34 on level 1 (E01), for a total of 63 (with 0 in the basement).",
     "model": "gemini-4-hydrogen",
     "cost_usd": 0.024636,
     "parts": [
      {
       "file": "set/H-101 E00 heating.png",
       "level": "low",
       "level_text": "Low confidence: read from the file's fact sheet, not yet measured. Check it before you use it.",
       "route": "raster",
       "facts": "Total space heaters: 29\nSpace heaters by type:\n- Heizkörper Plan Ventil Unten:Rechts: 29 (100.0%)",
       "scale": "1:100, printed scale bar (one bar)",
       "image": "h101",
       "marks": [[0.07, 0.098, 0.075, 0.114], [0.155, 0.098, 0.16, 0.114], [0.241, 0.098, 0.246, 0.114], [0.326, 0.098, 0.331, 0.114], [0.412, 0.098, 0.417, 0.114], [0.498, 0.098, 0.503, 0.114], [0.583, 0.098, 0.588, 0.114], [0.669, 0.098, 0.674, 0.114], [0.755, 0.098, 0.76, 0.114], [0.029, 0.161, 0.034, 0.177], [0.794, 0.165, 0.799, 0.181], [0.559, 0.431, 0.564, 0.447], [0.265, 0.435, 0.27, 0.451], [0.268, 0.488, 0.273, 0.505], [0.556, 0.492, 0.561, 0.509], [0.559, 0.546, 0.564, 0.562], [0.265, 0.55, 0.27, 0.566], [0.794, 0.577, 0.799, 0.594], [0.029, 0.817, 0.034, 0.833], [0.069, 0.883, 0.074, 0.9], [0.155, 0.883, 0.16, 0.9], [0.24, 0.883, 0.245, 0.9], [0.39, 0.883, 0.395, 0.9], [0.432, 0.883, 0.438, 0.9], [0.475, 0.883, 0.48, 0.9], [0.518, 0.883, 0.523, 0.9], [0.582, 0.883, 0.588, 0.9], [0.668, 0.883, 0.673, 0.9], [0.754, 0.883, 0.759, 0.9]],
       "check": {
        "reason": "Please double-check this answer against the file: it is read from its fact sheet, and such answers are not yet measured."
       },
       "explanation": "read from the file's fact sheet; not yet measured, so confidence is Low"
      },
      {
       "file": "set/H-102 E01 heating.png",
       "level": "low",
       "level_text": "Low confidence: read from the file's fact sheet, not yet measured. Check it before you use it.",
       "route": "raster",
       "facts": "Total space heaters: 34\nSpace heaters by type:\n- Heizkörper Plan Ventil Unten:Rechts: 34 (100.0%)",
       "scale": "1:100, printed scale bar (one bar)",
       "image": "h102",
       "marks": [[0.07, 0.098, 0.076, 0.117], [0.155, 0.098, 0.161, 0.117], [0.22, 0.098, 0.225, 0.117], [0.262, 0.098, 0.267, 0.117], [0.326, 0.098, 0.332, 0.117], [0.412, 0.098, 0.417, 0.117], [0.498, 0.098, 0.503, 0.117], [0.583, 0.098, 0.588, 0.117], [0.669, 0.098, 0.674, 0.117], [0.754, 0.098, 0.76, 0.117], [0.029, 0.162, 0.034, 0.181], [0.794, 0.165, 0.799, 0.184], [0.559, 0.433, 0.564, 0.451], [0.029, 0.434, 0.034, 0.452], [0.794, 0.437, 0.799, 0.455], [0.555, 0.463, 0.56, 0.481], [0.559, 0.49, 0.565, 0.509], [0.265, 0.492, 0.27, 0.511], [0.269, 0.52, 0.274, 0.539], [0.029, 0.545, 0.034, 0.564], [0.794, 0.548, 0.799, 0.567], [0.265, 0.55, 0.27, 0.568], [0.029, 0.817, 0.034, 0.835], [0.794, 0.82, 0.799, 0.838], [0.069, 0.883, 0.074, 0.902], [0.155, 0.883, 0.16, 0.902], [0.24, 0.883, 0.245, 0.902], [0.326, 0.883, 0.331, 0.902], [0.411, 0.883, 0.416, 0.902], [0.497, 0.883, 0.502, 0.902], [0.56, 0.883, 0.565, 0.902], [0.603, 0.883, 0.608, 0.902], [0.668, 0.883, 0.673, 0.902], [0.753, 0.883, 0.759, 0.902]],
       "check": {
        "reason": "Please double-check this answer against the file: it is read from its fact sheet, and such answers are not yet measured."
       },
       "explanation": "read from the file's fact sheet; not yet measured, so confidence is Low"
      },
      {
       "file": "services/rwth-digitalhub_digitalhub-fm-hzg-v2.ifc",
       "level": "low",
       "level_text": "Low confidence: read from the file's fact sheet, not yet measured. Check it before you use it.",
       "route": "bim",
       "facts": "Space heaters by storey:\n- Basement (B01_OKRD): 0\n- Ground floor (E00_OKRD): 29\n- Level 1 (E01_OKRD): 34\nTotal space heaters: 63\nCount by predefined type:\n- RADIATOR: 63 (100.0%)\nSpace heaters by type:\n- Heizkörper Plan Ventil Unten:Rechts: 63 (100.0%)",
       "check": {
        "reason": "Please double-check this answer against the file: it is read from its fact sheet, and such answers are not yet measured."
       },
       "explanation": "read from the file's fact sheet; not yet measured, so confidence is Low"
      }
     ]
    }
   ]
  };
  for (const ex of EXAMPLES) ex.turns = TURNS[ex.id];

  const find = (id) => EXAMPLES.find((x) => x.id === id) || null;

  // The part of the page an answer's figure shows, [x, y, w, h] in fractions: every mark and disputed place with a
  // margin, or, with a place in focus, a window around it in the page's own proportions.
  function viewOf(boxes, focus) {
    const clamp = ([x, y, w, h]) => {
      w = Math.min(1, w); h = Math.min(1, h);
      return [Math.min(Math.max(0, x), 1 - w), Math.min(Math.max(0, y), 1 - h), w, h];
    };
    if (focus) {
      const cx = (focus[0] + focus[2]) / 2, cy = (focus[1] + focus[3]) / 2, s = 0.16;
      return clamp([cx - s / 2, cy - s / 2, s, s]);
    }
    if (!boxes.length) return [0, 0, 1, 1];
    const x0 = Math.min(...boxes.map((b) => b[0])), y0 = Math.min(...boxes.map((b) => b[1]));
    const x1 = Math.max(...boxes.map((b) => b[2])), y1 = Math.max(...boxes.map((b) => b[3]));
    // a margin, and at least a third of the page each way, so a lone mark still shows the rooms around it
    const w = Math.max(x1 - x0 + 0.1, 1 / 3), h = Math.max(y1 - y0 + 0.1, 1 / 3);
    return clamp([(x0 + x1 - w) / 2, (y0 + y1 - h) / 2, w, h]);
  }

  const API = { EXAMPLES, find, viewOf };
  if (typeof module !== 'undefined' && module.exports) { module.exports = API; return; }

  // ---------- screens (browser only) ----------
  const esc = (s) => window.VPlan.esc(s);
  const A = () => window.VApp;
  const ST = {};  // per example: { asked: [turn index], focus: { 't-p': disputed index } }
  const state = (ex) => (ST[ex.id] = ST[ex.id] || { asked: [0], focus: {} });
  const LEVEL = { high: ['High', 'ok'], medium: ['Medium', 'acc'], low: ['Low', 'warn'] };
  const ROUTE = { raster: 'Read from the image by the image readers', vector: 'Read from the PDF\'s vector lines', bim: 'Read from the IFC model' };
  const pct = (n) => `${(n * 100).toFixed(2)}%`;

  // the page cropped to view, with the marks: counted ones green and numbered, disputed places amber
  function figure(ex, part, focusBox) {
    const img = ex.images[part.image], marks = part.marks || [], dis = (part.check && part.check.disputed) || [];
    const [vx, vy, vw, vh] = viewOf(marks.concat(dis.map((d) => d.box)), focusBox);
    const pos = ([x0, y0, x1, y1]) => `left:${pct((x0 - vx) / vw)};top:${pct((y0 - vy) / vh)};width:${pct((x1 - x0) / vw)};height:${pct((y1 - y0) / vh)}`;
    const flagged = new Set(dis.map((d) => d.mark));
    const spans = marks.map((b, i) => `<span class="hl${flagged.has(i + 1) ? '' : ' ok'}" style="${pos(b)}"><b>${i + 1}</b></span>`)
      .concat(dis.filter((d) => d.mark === null).map((d) => `<span class="hl open" style="${pos(d.box)}"><b>?</b></span>`)).join('');
    return `<div class="src ex-src" style="aspect-ratio:${(vw * img.w / (vh * img.h)).toFixed(3)}"><img src="../examples/${esc(img.src)}" alt="${esc(part.file)}"
      style="left:${pct(-vx / vw)};top:${pct(-vy / vh)};width:${pct(1 / vw)}">${spans}</div>`;
  }

  function partHtml(ex, t, ti, part, pi) {
    const key = `${ti}-${pi}`, focus = state(ex).focus[key], dis = (part.check && part.check.disputed) || [];
    const [word, tone] = LEVEL[part.level];
    const value = part.value === undefined ? `<p class="ex-facts">${esc(part.facts)}</p>`
      : `<div class="value"><b>${part.value}</b><span>${esc(part.noun)}</span></div>`;
    const places = dis.map((d, i) => `<li><button class="ref press" data-act="ex-focus" data-x="${ex.id}" data-k="${key}" data-i="${i}" aria-pressed="${focus === i}">
        <span class="num warn">${d.mark === null ? '?' : d.mark}</span><span><span style="font-weight:600">${esc(d.why)}</span>
        <span class="muted">${esc(Object.entries(d.readers).map(([r, s]) => `${r}: ${s}`).join(' · '))}</span></span></button></li>`).join('');
    const check = part.check ? `<div class="dc"><span><span class="pill warn on-surface">Please double-check</span></span><p>${esc(part.check.reason)}</p>
        ${places ? `<ol class="refs" aria-label="Places the readers disagree on">${places}</ol><p class="small">Tap a place to zoom to it on the drawing.</p>` : ''}</div>` : '';
    const how = [part.explanation || ROUTE[part.route], part.scale && `scale ${part.scale}`, part.rule && `rule: ${part.rule}`].filter(Boolean).join('; ');
    const side = `<div class="side">${value}<span><span class="pill ${tone}">${word}</span></span><p class="small">${esc(part.level_text)}</p>${check}
        <div style="display:flex;flex-direction:column;gap:4px"><span class="label">How it was found</span><p class="small">${esc(how)}.</p></div></div>`;
    if (!part.image) {
      return `<div class="card"><div class="side"><span class="mono" style="font-size:14px;font-weight:600">${esc(part.file)}</span><span class="small">IFC model · no picture</span></div>${side.replace('<div class="side">', '<div class="side" style="padding-top:0">')}</div>`;
    }
    const n = (part.marks || []).length;
    const legend = [n ? '<span><i class="lg" aria-hidden="true"></i>counted</span>' : '', dis.length ? '<span><i class="lg warn" aria-hidden="true"></i>the readers disagree here</span>' : ''].join('');
    return `<div class="card"><div class="answer"><figure data-fig="${ex.id}-${key}" aria-label="${esc(part.file)} with ${n} numbered marks">
        <span style="display:flex;flex-direction:column"><span class="mono" style="font-size:14px;font-weight:600">${esc(part.file)}</span><span class="small">${esc(ex.images[part.image].kind)}</span></span>
        ${figure(ex, part, focus === undefined || focus === null ? null : dis[focus].box)}
        <figcaption class="legend">${legend}${focus === undefined || focus === null ? '' : `<button class="btn btn-plain press" data-act="ex-focus" data-x="${ex.id}" data-k="${key}" data-i="${focus}" style="padding:6px 12px;font-size:13px">Show every mark</button>`}</figcaption></figure>
      ${side}</div></div>`;
  }

  function turnHtml(ex, ti) {
    const t = ex.turns[ti];
    return `<article class="turn"><p class="bubble">${esc(t.q)}</p><p class="lead">${esc(t.text)}</p>
      ${t.parts.map((p, pi) => partHtml(ex, t, ti, p, pi)).join('')}
      <p class="small">The chat's reply came from ${esc(t.model)}; this turn cost ${t.cost_usd.toFixed(3)} USD.</p></article>`;
  }

  function screen(r) {
    const ex = find(r.id), st = state(ex);
    const left = ex.turns.map((t, i) => [t, i]).filter(([, i]) => !st.asked.includes(i));
    const chips = left.length ? `<div class="chips-row" aria-label="Questions we asked">${left.map(([t, i]) => `<button class="qchip press" data-act="ex-ask" data-x="${ex.id}" data-i="${i}">${esc(t.q)}</button>`).join('')}</div>` : '';
    const others = EXAMPLES.filter((x) => x !== ex).map((x) => `<a href="#/example/${x.id}">${esc(x.title)}</a>`).join(' · ');
    return `<main class="w1040 ask"><div class="title-row"><div><span class="kicker ok">Recorded from the full app, 15 November 2026</span><h1>${esc(ex.name)}</h1>
        <p class="muted" style="margin:0">${esc(ex.blurb)}</p></div><a class="btn btn-plain press" href="#/">Back to the start</a></div>
      ${st.asked.map((i) => turnHtml(ex, i)).join('')}${chips}
      <p class="small">${esc(ex.credit[0])} <a href="${esc(ex.credit[1])}">Source</a>. These are questions we asked the app during the event; the full app is offline now, so this page replays what it answered.</p>
      <p class="small">More examples: ${others}</p></main>`;
  }

  // the start page's list: one card per example
  function cards() {
    return `<section class="results" aria-labelledby="ex-title"><h2 id="ex-title">Answers the full app gave</h2>
        <p>Recorded during the event on drawings we may publish: the questions we asked, the app's answers, its marks and how sure it was.</p>
        <div class="ex-cards">${EXAMPLES.map((x) => { const img = Object.values(x.images)[0];
          return `<a class="ex-card press" href="#/example/${x.id}"><img src="../examples/${esc(img.src)}" alt="" loading="lazy"><span class="ex-card-t">${esc(x.title)}</span><span class="small">${esc(x.blurb)}</span></a>`; }).join('')}</div>
      </section>`;
  }

  const actions = {
    'ex-ask': (el) => { const st = state(find(el.dataset.x)); st.asked.push(Number(el.dataset.i)); },
    // on a phone the figure sits above the list of places: bring it into view to show the zoom
    'ex-focus': (el) => {
      const f = state(find(el.dataset.x)).focus, i = Number(el.dataset.i), k = el.dataset.k;
      f[k] = f[k] === i ? null : i;
      requestAnimationFrame(() => { const fig = document.querySelector(`[data-fig="${el.dataset.x}-${k}"]`); if (fig) fig.scrollIntoView({ block: 'nearest' }); });
    },
  };

  root.VExamples = { ...API, screen, cards, actions };
})(typeof window !== 'undefined' ? window : globalThis);
