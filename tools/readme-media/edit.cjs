// The plan-edit GIF's frames: in the chat of a drawn plan, with a country's building rules picked,
// drag a box on the plan, ask for a room there, toggle before and after, scroll to the rule check.
//
//   node edit.cjs <app URL> <drawn PDF> <frames dir>
//
// PACK (rule pack, default "ch-zh"), BOX (the dragged box as page fractions "x0,y0,x1,y1", wider
// than 0.031 or the chat takes it for a click on a room; the default sits in Stanza 1.06 of the
// README's floor), ASK (default "Put a storage room here").
const { start, upload } = require('./lib.cjs');

const [base, pdf, out] = process.argv.slice(2);
if (!base || !pdf || !out) {
  console.error('usage: node edit.cjs <app URL> <drawn PDF> <frames dir>');
  process.exit(2);
}
const pack = process.env.PACK ?? 'ch-zh';
const [x0, y0, x1, y1] = (process.env.BOX ?? '0.615,0.412,0.652,0.493').split(',').map(Number);
const message = process.env.ASK ?? 'Put a storage room here';

(async () => {
  const rec = await start({ out });
  const p = rec.page;
  const { id } = await upload(p, base, pdf);
  await p.goto(`${base}/#/p/${id}/chat?pack=${pack}`);
  await p.getByRole('button', { name: 'Point at the plan' }).waitFor();
  await p.waitForTimeout(800);
  await rec.begin();
  await rec.hold(1300);
  await rec.click(p.getByRole('button', { name: 'Point at the plan' }));
  const region = p.getByRole('region', { name: 'Point at the plan' });
  const frame = region.locator('.vw-frame');
  const scroll = region.locator('.vw-scroll');
  await frame.locator('img').waitFor();
  await rec.hold(900);
  await scroll.evaluate((s) => s.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  await rec.hold(1200);
  const zoomIn = region.getByRole('button', { name: 'Zoom in' });
  await rec.click(zoomIn);
  await rec.hold(500);
  await rec.click(zoomIn);
  await scroll.evaluate(
    (s) =>
      new Promise((done) => {
        const wait = () =>
          s.scrollWidth > s.clientWidth * 3 ? done() : requestAnimationFrame(wait);
        wait();
      }),
  );
  await scroll.evaluate(
    (s, [x0, y0, x1, y1]) => {
      const el = s.querySelector('.vw-frame');
      s.scrollTo({
        left: ((x0 + x1) / 2) * el.clientWidth - s.clientWidth / 2 - 40,
        top: ((y0 + y1) / 2) * el.clientHeight - s.clientHeight / 2,
        behavior: 'smooth',
      });
    },
    [x0, y0, x1, y1],
  );
  await rec.hold(2200);
  const r = await frame.boundingBox();
  await rec.moveTo({ x: r.x + x0 * r.width, y: r.y + y0 * r.height });
  await rec.hold(250);
  await p.mouse.down();
  await rec.moveTo({ x: r.x + x1 * r.width, y: r.y + y1 * r.height }, { ms: 900 });
  await rec.hold(350);
  await p.mouse.up();
  await p.getByRole('button', { name: /^Remove Area on / }).waitFor();
  await rec.hold(1200);
  await rec.type(p.getByRole('textbox', { name: 'Question' }), message);
  await rec.click(p.getByRole('button', { name: 'Ask' }));
  const card = p.locator('.ag-card--edit');
  await card.waitFor({ timeout: 120_000 });
  await rec.hold(3600);
  await rec.click(card.getByRole('button', { name: 'Before' }));
  await rec.hold(1500);
  await rec.click(card.getByRole('button', { name: 'After' }));
  await rec.hold(1500);
  const law = card.getByRole('region', { name: /^Building rules/ });
  await rec.moveTo(law, { dy: -40 });
  await law.evaluate((el) =>
    window.scrollBy({
      top: el.getBoundingClientRect().top - 110,
      behavior: 'smooth',
    }),
  );
  await rec.hold(5000);
  await rec.stop(2500);
})();
