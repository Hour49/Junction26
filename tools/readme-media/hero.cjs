// The hero GIF's frames: upload an image of a plan on the start page, wait for the reading (played
// faster), ask one question in the chat, open the answer on the plan, zoom in on the marks.
//
//   node hero.cjs <app URL> <image file> <frames dir>
//
// QUESTION (default "How many toilets are there?"), MARK (a double-check mark to click at the end,
// e.g. "Mark 2"; none by default), PLAN_AT (where the plan sits on its sheet as page fractions,
// default "0.5,0.42"). Start the app with a fresh env.sh: a file it has seen is not read again.
const { start, pan, zoomed } = require('./lib.cjs');

const [base, image, out] = process.argv.slice(2);
if (!base || !image || !out) {
  console.error('usage: node hero.cjs <app URL> <image file> <frames dir>');
  process.exit(2);
}
const question = process.env.QUESTION ?? 'How many toilets are there?';
const [fx, fy] = (process.env.PLAN_AT ?? '0.5,0.42').split(',').map(Number);

(async () => {
  const rec = await start({ out });
  const p = rec.page;
  await p.goto(base);
  await p.getByRole('button', { name: 'Choose a file' }).waitFor();
  await p.waitForTimeout(800);
  await rec.begin();
  await rec.hold(1500);
  const chooser = p.waitForEvent('filechooser');
  await rec.click(p.getByRole('button', { name: 'Choose a file' }));
  await (await chooser).setFiles(image);
  await rec.hold(1000);
  rec.speed = 4; // the wait for the reading is shortened
  await p.getByText('Ready', { exact: true }).waitFor({ timeout: 300_000 });
  rec.speed = 1;
  console.log('read:', p.url());
  await rec.hold(2000);
  await rec.click(
    p
      .getByRole('button', { name: 'Start a new chat' })
      .or(p.getByRole('link', { name: 'Start a new chat' }))
      .first(),
  );
  await p.getByRole('button', { name: 'Point at the plan' }).waitFor();
  await rec.hold(700);
  await rec.type(p.getByRole('textbox', { name: 'Question' }), question);
  await rec.click(p.getByRole('button', { name: 'Ask' }));
  await p.locator('.ag-card').first().waitFor({ timeout: 120_000 });
  await rec.hold(3200);
  await rec.click(p.getByText(/^Show it on /).first());
  await p.getByRole('button', { name: 'Zoom in' }).first().waitFor();
  await rec.hold(2200);
  await rec.click(p.getByRole('button', { name: 'Zoom in' }).first());
  await zoomed(p);
  await pan(p, fx, fy, { dy: 60, smooth: true }); // the zoom keeps the sheet's top-left corner
  await rec.hold(2600);
  if (process.env.MARK) await rec.click(p.getByText(process.env.MARK, { exact: true }));
  await rec.hold(3500);
  await rec.stop(2500);
})();
