// Draws a drawing from data.js as inline SVG, in the look of a source file, with answer marks on top.
(function () {
  'use strict';
  const V = window.VData;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  // How each source kind looks: page fill, wall stroke and width, room fill, label colour and font.
  const LOOK = {
    clean: { bg: null, wall: '#2c3140', w: 4, room: '#ffffff', label: '#48484a', out: '#f3f3f6', font: 'Inter, system-ui, sans-serif' },
    cad: { bg: '#16181d', wall: '#9aa0aa', w: 1.5, room: 'none', label: '#6b7280', out: 'none', font: 'ui-monospace, Menlo, monospace' },
    pdf: { bg: '#ffffff', wall: '#1d1d1f', w: 3, room: 'none', label: '#48484a', out: 'none', font: 'Inter, system-ui, sans-serif' },
    raster: { bg: '#f1f0ec', wall: '#3a3a3c', w: 3.5, room: '#fbfaf7', label: '#636366', out: 'none', font: 'Inter, system-ui, sans-serif', blur: 0.8 },
    scan: { bg: '#f3eedd', wall: '#5b4a33', w: 3, room: '#f8f3e4', label: '#6b5a40', out: 'none', font: 'Georgia, serif', blur: 0.9 },
  };
  const ACCENT = '#3d5a4f', WARN = '#d9860b';

  function lookOfFile(kind) {
    if (/DXF|DWG|IFC/.test(kind)) return 'cad';
    if (/PDF/.test(kind)) return 'pdf';
    if (/PNG/.test(kind)) return 'raster';
    return 'scan';
  }

  function base(d, lookName, uid) {
    const L = V.layoutOf(d), k = LOOK[lookName];
    const [vx, vy, vw, vh] = L.view;
    let s = '';
    if (k.bg) s += `<rect x="${vx}" y="${vy}" width="${vw}" height="${vh}" fill="${k.bg}"/>`;
    if (k.blur) s += `<defs><filter id="blur-${uid}"><feGaussianBlur stdDeviation="${k.blur}"/></filter></defs>`;
    s += `<g${k.blur ? ` filter="url(#blur-${uid})"` : ''}>`;
    s += `<g fill="${k.out}" stroke="${k.wall}" stroke-width="${Math.max(1, k.w / 2)}" stroke-dasharray="6 4">`
      + L.outdoor.map(([x, y, w, h]) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`).join('') + '</g>';
    s += `<g fill="${k.room}" stroke="${k.wall}" stroke-width="${k.w}">`
      + V.rooms(d).map((r) => `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}"/>`).join('') + '</g>';
    s += `<g font-family="${k.font}" font-size="${Math.max(8, Math.round(vw / 52))}" font-weight="600" fill="${k.label}" text-anchor="middle">`
      + V.rooms(d).map((r) => `<text x="${r.x + r.w / 2}" y="${r.y + r.h / 2 + 4}">${esc(r.label)}</text>`).join('') + '</g>';
    return s + '</g>';
  }

  function svgOpen(d, label, extraClass) {
    const [vx, vy, vw, vh] = V.layoutOf(d).view;
    return `<svg class="plan ${extraClass || ''}" viewBox="${vx} ${vy} ${vw} ${vh}" role="img" aria-label="${esc(label)}">`;
  }

  // A plain drawing, no marks (the drawing card and the advanced panels).
  function plain(d, lookName, label) {
    return svgOpen(d, label || `${d.name}, ${lookName === 'clean' ? 'drawing' : 'source file'}`) + base(d, lookName, `${d.id}-${lookName}`) + '</svg>';
  }

  // The answer plan. opts: { flagged: Map id → why, rejected: Set, added: Set, fixing: bool, turn: turn id }.
  function answerPlan(d, a, opts) {
    const flagged = opts.flagged || new Map(), rej = opts.rejected || new Set(), add = opts.added || new Set();
    let s = svgOpen(d, `${d.name} with ${a.marks.filter((m) => m.n).length} numbered marks`) + base(d, 'clean', `${d.id}-a`);
    for (const m of a.marks) {
      const isFlag = flagged.has(m.id), out = rej.has(m.id);
      const act = opts.fixing && !m.excluded ? ` data-act="toggle-mark" data-t="${opts.turn}" data-mark="${m.id}" role="button" tabindex="0"` : '';
      const name = m.missed ? 'missed place' : m.excluded ? 'open doorway, left out by the rule' : `mark ${m.n}`;
      const aria = ` aria-label="${esc(name + (out ? ', rejected' : '') + (isFlag ? `, not sure: ${flagged.get(m.id)}` : ''))}"`;
      if (m.room) {
        const r = m.room, fill = out ? 'rgba(142,142,147,0.10)' : 'rgba(61,90,79,0.12)';
        s += `<g class="mark" data-id="${m.id}"${act}${aria}><rect x="${r.x + 4}" y="${r.y + 4}" width="${r.w - 8}" height="${r.h - 8}" rx="6" fill="${fill}" stroke="${out ? '#aeaeb2' : ACCENT}" stroke-width="2.5"/>`;
        if (isFlag) s += `<rect x="${r.x + 1}" y="${r.y + 1}" width="${r.w - 2}" height="${r.h - 2}" rx="8" fill="none" stroke="${WARN}" stroke-width="2.5" stroke-dasharray="6 4"/>`;
        s += `<g font-family="Inter, system-ui, sans-serif" font-weight="700" text-anchor="middle"><circle cx="${r.x + 18}" cy="${r.y + 18}" r="11" fill="${out ? '#aeaeb2' : ACCENT}"/><text x="${r.x + 18}" y="${r.y + 22}" font-size="11" fill="#fff">${m.n}</text>`
          + `<text x="${r.x + r.w / 2}" y="${r.y + r.h / 2 + 20}" font-size="11" fill="${out ? '#8e8e93' : ACCENT}">${r.area.toFixed(1)} m²</text>`
          + (isFlag ? `<circle cx="${r.x + r.w - 16}" cy="${r.y + 16}" r="10" fill="${WARN}" stroke="#fff" stroke-width="2.5"/><text x="${r.x + r.w - 16}" y="${r.y + 20}" font-size="12" fill="#fff">?</text>` : '')
          + '</g></g>';
        continue;
      }
      s += `<g class="mark" data-id="${m.id}"${act}${aria} font-family="Inter, system-ui, sans-serif" font-size="11" font-weight="700" text-anchor="middle">`;
      if (m.excluded) {
        s += `<circle cx="${m.x}" cy="${m.y}" r="11" fill="#fff" stroke="#8e8e93" stroke-width="2" stroke-dasharray="3 2"/>`;
      } else if (m.missed) {
        const on = add.has(m.id);
        s += `<circle cx="${m.x}" cy="${m.y}" r="11" fill="${on ? ACCENT : '#fff'}" stroke="${on ? ACCENT : WARN}" stroke-width="2" stroke-dasharray="${on ? '0' : '3 2'}"/><text x="${m.x}" y="${m.y + 4}" font-size="13" fill="${on ? '#fff' : WARN}">+</text>`;
      } else {
        const fill = out || !m.counted ? '#aeaeb2' : ACCENT;
        s += `<circle cx="${m.x}" cy="${m.y}" r="11" fill="${fill}"/><text x="${m.x}" y="${m.y + 4}" fill="#fff">${m.n || '?'}</text>`;
      }
      if (isFlag) s += `<circle cx="${m.x}" cy="${m.y}" r="17" fill="none" stroke="${WARN}" stroke-width="2.5" stroke-dasharray="5 3"/><circle cx="${m.x + 15}" cy="${m.y - 15}" r="8" fill="${WARN}" stroke="#fff" stroke-width="2"/><text x="${m.x + 15}" y="${m.y - 11}" font-size="11" fill="#fff">?</text>`;
      s += '</g>';
    }
    return s + '</svg>';
  }

  // The original file with what the answer used highlighted, in that file's look.
  function original(d, file, a) {
    const look = lookOfFile(file.kind), counted = a.marks.filter((m) => m.counted);
    const noun = V.noun(a.quantity, 2);
    let s = svgOpen(d, `${file.path} with the ${counted.length} ${noun} of the answer highlighted`) + base(d, look, `${d.id}-o-${look}`);
    const box = (x, y, w, h) => {
      if (look === 'cad') return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="rgba(255,214,10,0.14)" stroke="#ffd60a" stroke-width="1.5" stroke-dasharray="4 3"/>`;
      if (look === 'pdf') return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" fill="none" stroke="${ACCENT}" stroke-width="2"/>`;
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4" fill="none" stroke="${ACCENT}" stroke-width="2"/><rect x="${x}" y="${y - 12}" width="${Math.min(w, 40)}" height="12" rx="3" fill="${ACCENT}"/><text x="${x + Math.min(w, 40) / 2}" y="${y - 3}" font-family="Inter, system-ui, sans-serif" font-size="8.5" font-weight="700" fill="#fff" text-anchor="middle">${esc(V.noun(a.quantity, 1).replace('m²', 'room'))}</text>`;
    };
    for (const m of counted) s += m.room ? box(m.room.x + 6, m.room.y + 6, m.room.w - 12, m.room.h - 12) : box(m.x - 14, m.y - 14, 28, 28);
    const [vx, vy] = V.layoutOf(d).view;
    const layer = { door: 'DOOR', window: 'WINDOW', room: 'ROOM', area: 'ROOM' }[a.quantity];
    const unit = layer === 'ROOM' ? 'POLYLINES' : 'BLOCKS';
    const caption = file.kind === 'IFC model' ? `IFC${layer === 'ROOM' ? 'SPACE' : layer} · ${counted.length} OBJECTS` : look === 'cad' ? `LAYER ${layer} · ${counted.length} ${unit}` : '';
    if (caption) s += `<text x="${vx + 14}" y="${vy + 14}" font-family="ui-monospace, Menlo, monospace" font-size="11" font-weight="600" fill="#ffd60a">${caption}</text>`;
    return s + '</svg>';
  }

  // A small thumbnail for the unpack film strip.
  function thumb(file) {
    if (!file.drawing) {
      return `<svg class="thumb" viewBox="0 0 120 156" aria-hidden="true"><rect width="120" height="156" rx="8" fill="#2c2c2e"/><path d="M30 30h44l16 16v80H30z" fill="#3a3a3c" stroke="#636366"/><text x="60" y="140" font-family="ui-monospace, monospace" font-size="10" fill="#8e8e93" text-anchor="middle">${esc(file.kind)}</text></svg>`;
    }
    const d = V.drawing(file.drawing);
    return plain(d, lookOfFile(file.kind), file.path).replace('class="plan ', 'class="plan thumb ');
  }

  window.VPlan = { plain, answerPlan, original, thumb, lookOfFile, esc };
})();
