// Recorder for the README media: lossless screencast frames with a time and a speed each, a drawn
// cursor (headless Chromium paints none), smooth mouse moves, and an upload helper. togif.py turns
// the frames into a GIF. Run with NODE_PATH=frontend/node_modules (Playwright comes from there).
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const CURSOR = `(() => {
  const install = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;left:0;top:0;width:24px;height:24px;transform:translate(-100px,-100px)';
    c.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M3 2 L3 19 L8 14.5 L11.2 22 L14 20.8 L10.8 13.5 L17.5 13.5 Z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    const ring = document.createElement('div');
    ring.style.cssText = 'position:absolute;left:-13px;top:-13px;width:30px;height:30px;border-radius:50%;background:rgba(61,90,76,.35);opacity:0;transition:opacity .25s';
    c.prepend(ring);
    document.documentElement.appendChild(c);
    addEventListener('mousemove', (e) => { c.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)'; }, true);
    addEventListener('mousedown', () => { ring.style.transition = 'none'; ring.style.opacity = '1'; }, true);
    addEventListener('mouseup', () => { ring.style.transition = 'opacity .35s'; ring.style.opacity = '0'; }, true);
  };
  if (document.documentElement) install();
  addEventListener('DOMContentLoaded', install);
})();`;

/** A page that records into `out`: frames as PNG plus frames.json ({name, t, speed} per frame). */
async function start({ out, width = 1200, height = 800 }) {
  fs.rmSync(out, { recursive: true, force: true });
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width, height } });
  await context.addInitScript(CURSOR);
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const frames = [];
  // speed: frames taken while it is N play N times faster (a wait that is shortened in the GIF)
  const rec = { page, speed: 1, pos: { x: width / 2, y: height / 2 } };
  let n = 0;
  cdp.on('Page.screencastFrame', (f) => {
    const name = String(++n).padStart(5, '0') + '.png';
    fs.writeFileSync(path.join(out, name), Buffer.from(f.data, 'base64'));
    frames.push({ name, t: Date.now(), speed: rec.speed });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  rec.begin = async () => {
    await page.mouse.move(rec.pos.x, rec.pos.y);
    await page.waitForTimeout(100);
    await cdp.send('Page.startScreencast', { format: 'png', everyNthFrame: 1 });
  };
  rec.hold = (ms) => page.waitForTimeout(ms);
  /** Move the cursor to a locator's centre (plus dx, dy) or to a point, eased over `ms`. */
  rec.moveTo = async (target, { ms = 550, dx = 0, dy = 0 } = {}) => {
    let x, y;
    if (typeof target.boundingBox === 'function') {
      await target.scrollIntoViewIfNeeded();
      const b = await target.boundingBox();
      x = b.x + b.width / 2 + dx;
      y = b.y + b.height / 2 + dy;
    } else ({ x, y } = target);
    const steps = Math.max(2, Math.round(ms / 16));
    const { x: x0, y: y0 } = rec.pos;
    for (let i = 1; i <= steps; i++) {
      const k = i / steps;
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e);
      await page.waitForTimeout(14);
    }
    rec.pos = { x, y };
  };
  rec.click = async (target, opts) => {
    await rec.moveTo(target, opts);
    await page.waitForTimeout(150);
    await page.mouse.down();
    await page.waitForTimeout(90);
    await page.mouse.up();
  };
  rec.type = async (locator, text) => {
    await rec.click(locator);
    await locator.pressSequentially(text, { delay: 38 });
    await page.waitForTimeout(350);
  };
  /** Stop and write frames.json; the last frame stays `tailMs` on screen. */
  rec.stop = async (tailMs = 2500) => {
    await page.waitForTimeout(300);
    await cdp.send('Page.stopScreencast');
    frames.push({ name: null, t: Date.now() + tailMs, speed: 1 });
    fs.writeFileSync(path.join(out, 'frames.json'), JSON.stringify(frames));
    await browser.close();
  };
  return rec;
}

/** Uploads one file as a project through the API and waits until it is read: {id, drawings}. */
async function upload(page, base, file, name = path.basename(file)) {
  const started = await page.request.post(`${base}/api/projects?name=${encodeURIComponent(name)}`, {
    data: fs.readFileSync(file),
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  if (started.status() !== 202) throw new Error(`upload of ${name}: ${started.status()}`);
  const { id } = await started.json();
  for (let i = 0; i < 300; i++) {
    const project = await (await page.request.get(`${base}/api/projects/${id}`)).json();
    if (project.state === 'done') {
      return {
        id,
        drawings: project.files.map((f) => f.drawing_id).filter(Boolean),
      };
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`${name} was not read within 300 s`);
}

/** Scrolls the visible, zoomed plan viewer so the page fraction (fx, fy) sits in its middle (plus dy px). */
function pan(page, fx, fy, { dy = 0, smooth = false } = {}) {
  return page.evaluate(
    ([fx, fy, dy, smooth]) => {
      const s = [...document.querySelectorAll('.vw-scroll')].find(
        (el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth * 1.5,
      );
      const frame = s.querySelector('.vw-frame');
      s.scrollTo({
        left: fx * frame.clientWidth - s.clientWidth / 2,
        top: fy * frame.clientHeight - s.clientHeight / 2 + dy,
        behavior: smooth ? 'smooth' : 'auto',
      });
    },
    [fx, fy, dy, smooth],
  );
}

/** Waits until a visible plan viewer is zoomed (its page is wider than its scroll box). */
function zoomed(page, factor = 1.5) {
  return page.waitForFunction(
    (k) =>
      [...document.querySelectorAll('.vw-scroll')].some(
        (el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth * k,
      ),
    factor,
  );
}

module.exports = { start, upload, pan, zoomed };
