// File triage end to end (file-triage.md FT-21, FT-22, FT-14 at 390) on the sample's site photo. It needs a backend with
// triage on: `TRIAGE_CLASSIFIER=rules npx playwright test e2e/triage.spec.ts`; with triage off (the default run) it
// skips itself and the other specs see the sample as before.
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const NOTE = 'not described: no description model is set up, so it is not judged';

interface FileRow {
  id: string;
  path: string;
  triage: unknown;
}

test('FT-21: the site photo is set aside as not a floor plan, its trace and issue, then read as a plan', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const pid = await sampleDone(page);
  const project = (await (await page.request.get(`/api/projects/${pid}`)).json()) as {
    cost_usd: number;
    files: FileRow[];
  };
  const site = project.files.find((f) => f.path === 'photos/site.jpg');
  test.skip(!site?.triage, 'triage is off: run with TRIAGE_CLASSIFIER=rules');
  const fid = site?.id ?? '';
  expect(project.cost_usd).toBe(0);

  // Documents' file list (parity: Ingest has no file list): the row says what triage thinks, not the reason.
  await page.goto(`/#/p/${pid}/documents`);
  const files = page.getByRole('region', { name: 'Files' });
  await expect(files).toContainText('1 not a floor plan: kept, not read');
  const row = files.locator(`a[href$="/f/${fid}"]`);
  await expect(row).toContainText('Not a floor plan: not a drawing');
  await expect(row).toContainText('– Not judged');
  await expect(row).not.toContainText('P(plan)');
  await row.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-row', offline);

  // Documents' issues: one for it, "Not a floor plan" in its words, linking to its file page.
  const issue = page
    .getByRole('region', { name: 'Issues' })
    .locator('ul > li, ol > li')
    .filter({ has: page.getByRole('link', { name: 'Open the file' }), hasText: 'photos/site.jpg' });
  await expect(issue).toHaveCount(1);
  await expect(issue).toContainText('Not a floor plan');
  const call = issue.getByRole('link', { name: 'Open the file' });
  await expect(call).toHaveAttribute('href', `#/p/${pid}/f/${fid}`);
  await issue.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-issue', offline);
  await call.click();

  // The trace: not described, so the note once; nothing was paid for.
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/f/${fid}$`));
  const card = page.getByRole('region', { name: 'Is it a floor plan?' });
  await expect(
    card.getByRole('heading', { name: 'Not a floor plan: not a drawing' }),
  ).toBeVisible();
  await expect(card.getByText(NOTE, { exact: true })).toHaveCount(1);
  // FT-22 (parity): no "Does it belong to this project?" block and no verdict pill on the file page.
  await expect(card.getByText('Does it belong to this project?')).toHaveCount(0);
  await expect(card.getByText('– Not judged')).toHaveCount(0);
  // FT-5 (#183) and FT-23: an undescribed non-plan gets the call too, under "Your call".
  await expect(card.getByRole('heading', { name: 'Your call' })).toBeVisible();
  await expect(card.getByRole('button', { name: /^It is (not )?related$/ })).toHaveCount(2);
  await expect(card).toContainText(
    "Your call replaces the suggestion and settles this file's issue. It does not read the file as a plan.",
  );
  await expect(page.locator('dt', { hasText: /^Cost$/ }).locator('+ dd')).toHaveText('$0.00');
  const open = page.getByRole('link', { name: 'Open the drawing' });
  await expect(open).toHaveCount(0);
  const name = card.getByRole('textbox', { name: 'Your name' });
  const read = card.getByRole('button', { name: 'Read it as a floor plan' });
  if (testInfo.project.name === 'phone') {
    // FT-14: the name field and the button are tap targets.
    for (const target of [name, read]) {
      expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
  }
  // The upload itself is the only picture of a non-plan (a 1600 px PNG, ~2.4 MB): wait for it before the shot.
  const preview = card.getByRole('img', { name: 'photos/site.jpg as uploaded' });
  await expect
    .poll(() =>
      preview.evaluate(
        (el) => (el as HTMLImageElement).complete && (el as HTMLImageElement).naturalWidth,
      ),
    )
    .toBeGreaterThan(0);
  await card.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-trace', offline);

  // Read it as a floor plan: confirm, then the file is read and its drawing opens.
  await name.fill('Ana');
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toBe("Read photos/site.jpg as a floor plan? This can't be undone.");
    void dialog.accept();
  });
  await read.click();
  await expect(open).toBeVisible({ timeout: 30_000 });
  await expect(
    card.getByRole('heading', { name: /^Read as a floor plan on Ana.s call$/ }),
  ).toBeVisible();
  await expect(read).toHaveCount(0);
  await shot(page, testInfo, 'ft-read-as-plan', offline);

  await page.goto(`/#/p/${pid}/documents`);
  await expect(files).toContainText('No image set aside as not a floor plan');
  await expect(row).toContainText(/Read as a floor plan on Ana.s call/);
  expect(errors, 'no console or page errors').toEqual([]);
});
