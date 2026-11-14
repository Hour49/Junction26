// A judge's walk through one chat in the web UI: open the project's chat, type the messages, take a
// viewport screenshot after each answer lands and a full-page one at the end.
//   PLAYWRIGHT_DIR=<frontend>/node_modules/playwright node walk.mjs <frontend url> <pid> <outdir> <w> <h> "msg1" "msg2" ...
import fs from 'node:fs';
import path from 'node:path';
const { chromium } = await import(`${process.env.PLAYWRIGHT_DIR}/index.mjs`);
const [base, pid, out, w, h, ...messages] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: +w, height: +h }, baseURL: base, ...(+w < 500 ? { isMobile: true, hasTouch: true } : {}),
});
const page = await context.newPage();
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`/#/p/${pid}/chat`);
const box = page.getByRole('textbox', { name: 'Question' });
await box.waitFor({ timeout: 30000 });
await page.waitForTimeout(800);
await page.screenshot({ path: path.join(out, `00-empty-${w}.png`) });
const record = [];
let n = 0;
for (const message of messages) {
  n += 1;
  const t = Date.now();
  await box.fill(message);
  await page.getByRole('button', { name: /^(Ask|Send)$/ }).click();
  const turn = page.getByRole('article', { name: message }).last();
  await turn.waitFor({ timeout: 120000 });
  await page.waitForFunction(() => !document.querySelector('.en-pending'), null, { timeout: 180000 });
  await page.waitForTimeout(500);
  const ms = Date.now() - t;
  await page.screenshot({ path: path.join(out, `${String(n).padStart(2, '0')}-${w}.png`) });
  const text = (await turn.innerText()).trim();
  record.push({ n, message, ms, text });
  console.log(`t${n} ${ms} ms | ${text.replace(/\s+/g, ' ').slice(0, 200)}`);
}
await page.screenshot({ path: path.join(out, `99-full-${w}.png`), fullPage: true });
const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
fs.writeFileSync(path.join(out, `record-${w}.json`), JSON.stringify({ pid, w, h, record, errors, sideways }, null, 1));
console.log('console errors', errors.length, 'sideways px', sideways);
await browser.close();
