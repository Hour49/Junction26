// The viewer's Previous/Next page buttons (viewer/PageViewer.tsx) on a two-page drawing: a drawn plan whose page 2 is
// text, so ingest keeps both pages on one drawing. The buttons' tips must not take the click or the tap away from
// them (a `Tip wrap` turned off their pointer events).
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { drawingOf, noKeys, shot, watchErrors } from './support';
import { VIEWER_TIPS } from '../src/shell/tips-viewer';

/** A two-page PDF from the backend's own sample sheets: the sample's flat-b plan, then its text document. */
function twoPages(e2eDir: string): Buffer {
  const backend = path.join(e2eDir, '..', '..', 'backend');
  const code =
    'import io, sys, pypdfium2; from scripts.make_sample_archive import flat_sheet, text_pdf; ' +
    "a = pypdfium2.PdfDocument(flat_sheet('30.00 m²', room_bottom=104, room_area='8.06 m²').pdf()); " +
    'a.import_pages(pypdfium2.PdfDocument(text_pdf())); b = io.BytesIO(); a.save(b); ' +
    'sys.stdout.buffer.write(b.getvalue())';
  return execFileSync('uv', ['run', '--locked', 'python', '-c', code], { cwd: backend });
}

test('the Next and Previous page buttons work by click and by tap', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  await page.goto('/#/');
  await page.locator('input[type=file]').setInputFiles({
    name: 'set.pdf',
    mimeType: 'application/pdf',
    buffer: twoPages(testInfo.config.rootDir),
  });
  await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
  const pid = /#\/p\/([0-9a-f]{12})$/.exec(page.url())?.[1] ?? '';
  await expect
    .poll(
      async () =>
        ((await (await page.request.get(`/api/projects/${pid}`)).json()) as { state: string })
          .state,
      { timeout: 30_000 },
    )
    .toBe('done');
  const { id } = await drawingOf(page, pid, 'set.pdf');
  await page.goto(`/#/p/${pid}/d/${id}/engineer`);

  const press = testInfo.project.use.hasTouch
    ? (name: string) => page.getByRole('button', { name }).tap()
    : (name: string) => page.getByRole('button', { name }).click();
  const line = page.getByText(/^Page \d of 2/);
  await expect(line).toContainText('Page 1 of 2');
  await press('Next page');
  await expect(line).toContainText('Page 2 of 2');
  await expect(page.getByRole('button', { name: 'Next page' })).toBeDisabled();
  if (!testInfo.project.use.hasTouch) {
    // the locked button keeps its tip: hover reaches the wrapper while the button is disabled
    await page.mouse.move(0, 0); // Radix reopens a tip only after the pointer has left its trigger
    await page.getByRole('button', { name: 'Next page' }).hover({ force: true });
    await expect(page.getByRole('tooltip')).toHaveText(VIEWER_TIPS.nextPage);
  }
  await shot(page, testInfo, 'page-buttons-2', offline);
  await press('Previous page');
  await expect(line).toContainText('Page 1 of 2');
  await expect(page.getByRole('button', { name: 'Previous page' })).toBeDisabled();
  expect(errors).toEqual([]);
});
