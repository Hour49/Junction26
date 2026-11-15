// File triage end to end (file-triage.md FT-21, FT-22, FT-14 at 390) on the sample's site photo. It needs a backend with
// triage on: `TRIAGE_CLASSIFIER=rules npx playwright test e2e/triage.spec.ts`; with triage off (the default run) it
// skips itself and the other specs see the sample as before.
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';
import { VERDICT_LABEL } from '../src/ingest/triage';

// backend/app/core/ingest/triage.py NOTE_NO_DESCRIBER / NOTE_NO_DESCRIBER_JUDGED: with a judge, it is judged anyway
const NOTE = 'not described: no description model is set up, so it is not judged';
const NOTE_JUDGED = 'not described: no description model is set up';

interface FileRow {
  id: string;
  path: string;
  triage: { verdict: 'related' | 'unrelated' | 'unsure' | null } | null;
}

test('FT-21: the site photo is set aside as not a floor plan, its trace, then read as a plan', async ({
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

  // P7: Documents' "Set aside" list holds the photo (its reason in words) and links to its trace. (The issue and
  // its "Open the file" link move into the chat; not asserted here.)
  await page.goto(`/#/p/${pid}/documents`);
  const aside = page.getByRole('region', { name: 'Set aside' });
  const row = aside.getByRole('listitem').filter({ hasText: 'photos/site.jpg' });
  await expect(row).toContainText('Not a floor plan: not a drawing');
  // the judge's verdict as the file page would word it (asserted absent there, FT-22)
  const verdict = VERDICT_LABEL[site?.triage?.verdict ?? 'none'].pill;
  await row.scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'ft-row', offline);
  const call = row.getByRole('link', { name: 'How photos/site.jpg was read' });
  await expect(call).toHaveAttribute('href', `#/p/${pid}/f/${fid}`);
  await call.click();

  // The trace: not described, so the note once; nothing was paid for.
  await expect(page).toHaveURL(new RegExp(`#/p/${pid}/f/${fid}$`));
  const card = page.getByRole('region', { name: 'Is it a floor plan?' });
  await expect(
    card.getByRole('heading', { name: 'Not a floor plan: not a drawing' }),
  ).toBeVisible();
  const note = site?.triage?.verdict ? NOTE_JUDGED : NOTE;
  await expect(card.getByText(note, { exact: true })).toHaveCount(1);
  // FT-22 (parity): no "Does it belong to this project?" block and no verdict pill on the file page.
  await expect(card.getByText('Does it belong to this project?')).toHaveCount(0);
  await expect(card.getByText(verdict)).toHaveCount(0);
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

  // now a drawing: its card is on Documents, with the file's path
  await page.goto(`/#/p/${pid}/documents`);
  await expect(page.getByRole('region', { name: 'Drawings' })).toContainText('photos/site.jpg');
  await expect(
    page.getByRole('region', { name: 'Set aside' }).getByRole('listitem').filter({
      hasText: 'photos/site.jpg',
    }),
  ).toHaveCount(0);
  expect(errors, 'no console or page errors').toEqual([]);
});
