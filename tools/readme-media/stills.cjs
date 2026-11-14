// The README's still pictures, desktop at 2x and phone at 390 px.
//
//   node stills.cjs <app URL> <out dir> <scan of a plan> <drawn PDF> <unread sheets>
//
// <unread sheets> is a PDF or zip the readers get nothing from (the refusal example). The questions
// and places below fit the README's drawings: the HABS sheet of the Isaac Franklin House as the
// scan and make_plan.py's flat as the drawn PDF; change them with the drawings. Look at every
// picture before it goes into docs/media/.
const fs = require('node:fs');
const { chromium } = require('playwright');
const { upload, pan, zoomed } = require('./lib.cjs');

const [base, out, image, pdf, unread] = process.argv.slice(2);
if (!base || !out || !image || !pdf || !unread) {
  console.error('usage: node stills.cjs <app URL> <out dir> <scan> <drawn PDF> <unread sheets>');
  process.exit(2);
}
const HIGH = 'How many doors are there?'; // on the drawn PDF
// on the scan: a count with a double-check request, the mark to open, where the plan sits on the sheet
const CHECK = { ask: 'How many doors are there?', mark: 'Mark 19', at: [0.5, 0.5] };
const PHONE = 'How many toilets are there?'; // on the scan, in the chat at phone width
const REFUSED = ['How many doors are there?', 'Remove the wall between the kitchen and the hall'];
const EDIT = 'Remove the wall between Zimmer 1.01 and Zimmer 1.02';
const PACK = 'ch-zh';

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const desk = await browser.newContext({
    viewport: { width: 1200, height: 800 },
    deviceScaleFactor: 2,
  });
  const p = await desk.newPage();
  const img = await upload(p, base, image);
  const drawn = await upload(p, base, pdf);
  const none = await upload(p, base, unread);
  const shot = (page, name, clip) => page.screenshot({ path: `${out}/${name}.png`, clip });
  const chat = async (page, id, query = '') => {
    await page.goto(`${base}/#/p/${id}/chat${query}`);
    await page.reload();
    await page.getByRole('button', { name: 'Point at the plan' }).waitFor();
  };
  const ask = async (page, text, n) => {
    await page.getByRole('textbox', { name: 'Question' }).fill(text);
    await page.getByRole('button', { name: 'Ask' }).click();
    await page.locator('.ag-card').nth(n).waitFor({ timeout: 120_000 });
    await page.waitForTimeout(1500);
  };
  // the answer view of a drawing; with `zoomAt` the plan is zoomed in once on that place
  const engineer = async (project, question, zoomAt) => {
    const at = `${base}/#/p/${project.id}/d/${project.drawings[0]}`;
    await p.goto(`${at}/engineer?ask=${encodeURIComponent(question)}`);
    await p.reload();
    const zoomIn = p.getByRole('button', { name: 'Zoom in' }).first();
    await zoomIn.waitFor();
    await p.waitForTimeout(1500);
    if (zoomAt) {
      await zoomIn.click();
      await zoomed(p);
      await pan(p, ...zoomAt);
    }
    return at;
  };

  // an answer with marks and High confidence, from the drawn PDF
  const drawnAt = await engineer(drawn, HIGH);
  await p.waitForTimeout(1500);
  await shot(p, 'answer-high');
  // a scan: a double-check request that names the mark; the page is scrolled past the flag banner
  await engineer(img, CHECK.ask, CHECK.at);
  await p.getByText(CHECK.mark, { exact: true }).click();
  await p
    .getByRole('button', { name: 'Zoom in' })
    .first()
    .evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 150));
  await p.waitForTimeout(1500);
  await shot(p, 'answer-check');
  // the surveyor's takeoff table
  await p.goto(`${drawnAt}/surveyor`);
  await p.waitForTimeout(3000);
  await shot(p, 'takeoff');

  // two refusals with their reasons, cut to the two turns
  await p.setViewportSize({ width: 1200, height: 900 });
  await chat(p, none.id);
  await ask(p, REFUSED[0], 0);
  await ask(p, REFUSED[1], 1);
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(800);
  const first = await p.getByRole('article').first().boundingBox();
  const last = await p.locator('.ag-card').last().boundingBox();
  await shot(p, 'refusal', {
    x: last.x - 24,
    y: first.y - 20,
    width: last.width + 48,
    height: last.y + last.height - first.y + 44,
  });
  // the end of an edit card: what is not known, accept or reject, the agent's steps
  await chat(p, drawn.id, `?pack=${PACK}`);
  await ask(p, EDIT, 0);
  const card = p.locator('.ag-card--edit');
  await card.locator('.ag-steps summary').click();
  await card
    .getByText('Not known', { exact: true })
    .evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 110));
  await p.waitForTimeout(800);
  const c = await card.boundingBox();
  await shot(p, 'agent-steps', {
    x: c.x - 24,
    y: 84,
    width: c.width + 48,
    height: Math.min(c.y + c.height + 24, 890) - 84,
  });
  await desk.close();

  // phone width
  const phone = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });
  const m = await phone.newPage();
  await m.goto(base);
  await m.getByRole('button', { name: 'Choose a file' }).waitFor();
  await m.waitForTimeout(1000);
  await shot(m, 'phone-home');
  await chat(m, img.id);
  await ask(m, PHONE, 0);
  await shot(m, 'phone-answer');
  await chat(m, drawn.id, `?pack=${PACK}`);
  await ask(m, EDIT, 0);
  await m
    .locator('.ag-card--edit')
    .getByRole('region', { name: /^Building rules/ })
    .evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 120));
  await m.waitForTimeout(800);
  await shot(m, 'phone-rules');
  await browser.close();
})();
