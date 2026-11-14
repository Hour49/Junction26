// The golden demo path (docs/specs/frontend/golden-path.md, steps 1-12 and the conflicts list) on the
// live backend, at the project's viewport, with a screenshot of every screen.
import { readFile } from 'node:fs/promises';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { methodName } from '../src/api/format';
import { drawingOf, filesThrough, noKeys, shot, watchErrors } from './support';

const AREA = 'What is the net floor area of room 1.01?';

test('GP-1..GP-13, GP-28, GP-41..GP-52: the golden demo path', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const turn = (question: string) => page.getByRole('article', { name: question }).last();

  await test.step('GP-2 step 1: home', async () => {
    await page.goto('/#/');
    await expect(page.getByRole('button', { name: 'Try the sample project' })).toBeVisible();
    await shot(page, testInfo, '01-home', offline);
  });

  let pid = '';
  let flatB = { id: '', label: '' };
  await test.step('GP-3 GP-41 GP-42 GP-45 P2: the sample ingests; the finished screen', async () => {
    await page.getByRole('button', { name: 'Try the sample project' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
    pid = /#\/p\/([0-9a-f]{12})$/.exec(page.url())?.[1] ?? '';
    await expect(filesThrough(page)).toHaveText('12 / 12', { timeout: 30_000 });
    await expect(page.getByText('All 9 steps done').first()).toBeVisible();
    await expect(page.locator('dt', { hasText: 'Drawings ready' }).locator('+ dd')).toHaveText(
      '6 / 6',
    );
    flatB = await drawingOf(page, pid, 'plans/flat-b.pdf');
    // GP-41: exactly Ingest, Chat, Documents (no Conflicts, Issues, Checks or Surveyor tab).
    await expect(
      page.getByRole('banner').getByRole('navigation', { name: 'Views' }).getByRole('link'),
    ).toHaveText(['Ingest', 'Chat', /^Documents/]);
    const main = page.getByRole('main');
    await expect(main.getByText(/^6 drawings ready\. Conflicts are below\./)).toBeVisible();
    // GP-42: the conflicts under the progress card; the sample's one conflict is settled by the rule.
    const conflicts = main.getByRole('region', { name: 'Conflicts' });
    await expect(
      conflicts.getByRole('heading', { level: 2, name: '1 conflict found' }),
    ).toBeVisible();
    const card = kitchenCard(conflicts);
    await expect(card).toContainText(flatB.label);
    await expect(card).toContainText('Settled by rule');
    await expect(card).toContainText('22.40 m²');
    await expect(card).toContainText('30.00 m²');
    // No issues and no file list on Ingest: they are in Documents.
    await expect(main.getByRole('region', { name: 'Issues' })).toHaveCount(0);
    await expect(main.locator('a[href*="/f/f"]')).toHaveCount(0);
    // GP-45: nothing needs a person, so the chat is open; the workspace link is there.
    await expect(main.getByRole('link', { name: 'Start a new chat' })).toBeVisible();
    await expect(main.getByRole('link', { name: 'Open the workspace' })).toBeVisible();
    await shot(page, testInfo, '02-ingest-done', offline);
  });

  await test.step('GP-43 GP-44 P2a P2b: the source figure, minimized, expanded, previewed', async () => {
    const card = kitchenCard(page);
    const figure = card.getByRole('figure', { name: 'Source of conflict 1' });
    // Starts minimized: the thumbnail beside the legend.
    await expect(figure.getByRole('button', { name: 'Expand the drawing' })).toBeVisible();
    await expect(figure.getByRole('list').first()).toBeVisible();
    await figure.getByRole('button', { name: 'Expand', exact: true }).click();
    await expect(figure.getByRole('button', { name: 'Minimize', exact: true })).toBeVisible();
    await expect(figure.getByRole('img').first()).toBeVisible();
    await shot(page, testInfo, '02a-conflict-expanded', offline);
    await figure.getByRole('button', { name: 'Minimize', exact: true }).click();
    await expect(figure.getByRole('button', { name: 'Expand', exact: true })).toBeVisible();

    const show = figure.getByRole('button', { name: 'Show source' });
    await show.click();
    const dialog = page.getByRole('dialog', { name: `Source: ${flatB.label}` });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused();
    await shot(page, testInfo, '02b-show-source', offline);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(show).toBeFocused();
  });

  await test.step('GP-37 CF-22 CF-41: Modify, a variant, then back to the rule', async () => {
    const card = kitchenCard(page);
    await card.getByRole('button', { name: 'Modify' }).click();
    await expect(card.getByRole('textbox', { name: 'Or type your own answer' })).toBeVisible();
    await card.getByRole('button', { name: /^Variant 1:/ }).click();
    await expect(card).toContainText('Your choice');
    // GP-37 (Tudor): a person's choice keeps "Modify", never "Change".
    await expect(card.getByRole('button', { name: 'Modify' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Change', exact: true })).toHaveCount(0);
    await card.getByRole('button', { name: "Use the rule's value" }).click();
    await expect(card).toContainText('Settled by rule');
  });

  await test.step('GP-30 GP-46 P3: the Advanced view has the same finished layout', async () => {
    const view = page.getByRole('group', { name: 'View' });
    await view.getByRole('link', { name: 'Advanced' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\?view=advanced$/);
    await expect(page.getByRole('navigation', { name: 'Steps' })).toBeVisible();
    const main = page.getByRole('main');
    await expect(kitchenCard(main.getByRole('region', { name: 'Conflicts' }))).toBeVisible();
    await expect(main.getByRole('link', { name: 'Start a new chat' })).toBeVisible();
    await shot(page, testInfo, '03-advanced', offline);
    await view.getByRole('link', { name: 'Simple' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}$/);
  });

  await test.step('GP-47 P4: the old Conflicts and Issues routes land on Ingest', async () => {
    for (const old of ['conflicts', 'issues?pack=fi']) {
      await page.goto(`/#/p/${pid}/${old}`);
      await expect(
        page.getByRole('banner').getByRole('link', { name: 'Ingest', exact: true }),
      ).toHaveAttribute('aria-current', 'page');
      await expect(page.getByRole('main').getByRole('region', { name: 'Conflicts' })).toBeVisible();
    }
  });

  await test.step('GP-48 P5: Documents: issues, then drawings, then files', async () => {
    await page.goto(`/#/p/${pid}`);
    await page
      .getByRole('banner')
      .getByRole('link', { name: /^Documents/ })
      .click();
    await expect(page).toHaveURL(new RegExp(`#/p/${pid}/documents$`));
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
    const sections = main.getByRole('region');
    await expect(sections).toHaveText([/^Issues/, /^Drawings/, /^Files/]);
    const issues = (await (await page.request.get(`/api/projects/${pid}/issues`)).json()) as {
      issues: { severity: string; state: string }[];
    };
    const toAnswer = issues.issues.filter(
      (i) => i.state === 'open' && ['needs_person', 'fails_rule'].includes(i.severity),
    ).length;
    // SH-78: the tab's name carries the count; none on the sample.
    await expect(
      page.getByRole('banner').getByRole('link', { name: /^Documents/ }),
    ).toHaveAccessibleName(
      toAnswer ? new RegExp(`^Documents, ${String(toAnswer)} issues? to answer$`) : 'Documents',
    );
    await expect(main.getByRole('region', { name: 'Drawings' }).getByRole('listitem')).toHaveCount(
      6,
    );
    const files = main.getByRole('region', { name: 'Files' }).getByRole('link');
    await expect(files).toHaveCount(12);
    // A note is shown, never answered.
    await expect(main.getByRole('region', { name: 'Issues' }).getByRole('textbox')).toHaveCount(
      toAnswer ? toAnswer : 0,
    );
    await shot(page, testInfo, '05-documents', offline);
  });

  await test.step('GP-4 GP-49 step 3: the trace of plans/flat-b.pdf, from Documents', async () => {
    await page
      .getByRole('region', { name: 'Files' })
      .getByRole('link')
      .filter({ hasText: 'plans/flat-b.pdf' })
      .click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/f\/f\d+$/);
    await expect(page.getByRole('link', { name: 'Back to Documents' })).toBeVisible();
    await expect(page.getByText('flagged').first()).toBeVisible();
    await expect(page.getByText('1 conflict between the two methods').first()).toBeVisible();
    // IN-83: the stages are folded under "How it was read" like the demo's trace.
    await page
      .getByRole('region', { name: 'Stages' })
      .getByText(/^How it was read/)
      .click();
    await expect(page.getByText('5 quantities measured twice, 1 conflict').first()).toBeVisible();
    // the write stage's `did`
    await expect(page.getByText(/drawing model [0-9a-f]{16} stored/).first()).toBeVisible();
    await expect(page.getByText('Does it belong to this project?')).toHaveCount(0);
    await shot(page, testInfo, '04-trace', offline);
  });

  const DOORS = 'How many doors are there?';
  await test.step('GP-39 GP-40 GP-50 P7 P8: a new chat over the project, one question', async () => {
    await page.goto(`/#/p/${pid}`);
    await page.getByRole('link', { name: 'Start a new chat' }).click();
    await expect(page).toHaveURL(/#\/p\/[0-9a-f]{12}\/chat$/);
    await expect(
      page.getByRole('banner').getByRole('link', { name: 'Chat', exact: true }),
    ).toHaveAttribute('aria-current', 'page');
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { level: 1, name: 'sample-project.zip' })).toBeVisible();
    // Empty (chat.md): the heading, the ask bar and 3 suggestion chips; no plan, image or marks.
    await expect(main.locator('img, figure, canvas, svg image')).toHaveCount(0);
    await expect(main.getByRole('textbox', { name: 'Question' })).toBeVisible();
    await expect(main.getByRole('button', { name: 'Ask' })).toBeVisible();
    const chips = main.getByRole('group', { name: 'Suggested questions' }).getByRole('button');
    await expect(chips).toHaveText([
      DOORS,
      'What is the net floor area of all indoor rooms in m²?',
      'How many windows are there?',
    ]);
    await shot(page, testInfo, '05a-chat', offline);

    await chips.filter({ hasText: DOORS }).click();
    const answer = turn(DOORS);
    // Several drawings answer: no total (they may show the same rooms), then one line per drawing.
    await expect(answer.getByTestId('answer-value')).toHaveCount(0);
    await expect(answer).toContainText(/may show the same rooms/);
    // ui-bugs 4/6/8: the references under the image switch it and the one card beside it; no Show it on link
    await answer
      .getByRole('list', { name: 'References' })
      .getByRole('button', { name: new RegExp(flatB.label) })
      .click();
    const perDrawing = answer.getByRole('list', { name: 'Per drawing' });
    await expect(perDrawing.getByRole('listitem')).toHaveCount(1);
    await expect(perDrawing).toContainText(`${flatB.label}: 2`);
    await expect(answer.getByRole('link', { name: /^Show it on/ })).toHaveCount(0);
    // GP-50: the reference image with its name above (flat-b is the second reference, just clicked), the references list, follow-up chips.
    await expect(answer.getByRole('figure', { name: /^Reference 2 of \d+$/ })).toBeVisible();
    await expect(answer.getByRole('list', { name: 'References' })).toBeVisible();
    await expect(main.getByRole('group', { name: 'Suggested questions' })).toHaveCount(0);
    const followUps = main.getByRole('group', { name: 'Follow-up questions' }).getByRole('button');
    await expect(followUps.first()).toBeVisible();
    await shot(page, testInfo, '05b-chat-answer', offline);
  });

  let drawingUrl = '';
  await test.step('GP-32 GP-51 V6: the flat-b drawing opened as engineer, asking the chat question', async () => {
    // ui-bugs 8/13: the chat has no link to a drawing's workspace any more; its deep link opens it.
    await page.goto(
      `/#/p/${pid}/d/${flatB.id}/engineer?${new URLSearchParams({ ask: DOORS }).toString()}`,
    );
    await expect(page).toHaveURL(new RegExp(`#/p/${pid}/d/${flatB.id}/engineer(\\?.*)?$`));
    expect(new URLSearchParams(page.url().split('?')[1] ?? '').get('ask')).toBe(DOORS);
    drawingUrl = page.url().replace(/\/engineer(\?.*)?$/, '');
    const image = page.getByRole('img', { name: /^Page 1 of / }).first();
    await expect(image).toBeVisible();
    await expect
      .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
      .toBeGreaterThan(0);
    // GP-51: no credit line on screens (they are on the About page, GP-52).
    await expect(page.getByText(/^Credit:/)).toHaveCount(0);
    await shot(page, testInfo, '06-engineer', offline);
  });

  await test.step('GP-6 step 5: a count with its marks', async () => {
    // ?ask= asked the chat's question on open (EN-72): exactly one turn, no second ask.
    await expect(page.getByRole('article', { name: DOORS })).toHaveCount(1);
    const doors = turn(DOORS);
    await expect(doors.getByTestId('answer-value')).toHaveText('2');
    await expect(doors).toContainText('One method');
    await expect(doors.getByRole('button', { name: /^Mark \d+: door, counted$/ })).toHaveCount(2);
    // EN-43: the newest turn is scrolled into view
    await expect(doors).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '07-count', offline);
  });

  await test.step('GP-7 step 6: an area where the methods disagree', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill(AREA);
    await page.getByRole('button', { name: 'Ask' }).click();
    const area = turn(AREA);
    await expect(area.getByTestId('answer-value')).toHaveText('30.00 m²');
    await expect(area).toContainText('Methods disagree');
    await expect(area).toContainText(`22.40 m² by ${methodName('polygon_x_scale')}`);
    await expect(area).toContainText(`30.00 m² by ${methodName('printed_label')}`);
    await expect(area.getByRole('button', { name: 'Mark 1: Küche, counted' })).toHaveCount(1);
    // EN-43: the newest turn is scrolled into view
    await expect(area).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '08-area-conflict', offline);
  });

  await test.step('GP-8 step 7: a refusal', async () => {
    await page.getByRole('textbox', { name: 'Question' }).fill('What colour is the roof?');
    await page.getByRole('button', { name: 'Ask' }).click();
    const roof = turn('What colour is the roof?');
    await expect(roof).toContainText("I can't answer that from this drawing.");
    await expect(roof).toContainText("This question isn't one I can turn into a count");
    // The refusal code is not shown on the card (QA sign-off, #14).
    await expect(roof).not.toContainText('code:');
    await expect(roof).not.toContainText('unsupported-question');
    await expect(roof.getByRole('button', { name: 'How many doors are there?' })).toBeVisible();
    await expect(roof.getByTestId('answer-value')).toHaveCount(0);
    // EN-43: the newest turn is scrolled into view
    await expect(roof).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '09-refusal', offline);
  });

  await test.step('GP-9, GP-28 step 8: the surveyor queue and the conflicts list', async () => {
    // No Surveyor tab (SH-75) and no surveyor link on the conflict card (CF-47): the area answer sends it there.
    await turn(AREA).getByRole('link', { name: 'Send to surveyor' }).click();
    await expect(page).toHaveURL(new RegExp(`^${escape(drawingUrl)}/surveyor(\\?.*)?$`));
    for (const text of [
      'area of room (name Küche · 1.01)',
      '22.40 m² vs 30.00 m²',
      'decided by rule',
    ]) {
      await expect(page.getByText(text).first()).toBeVisible();
    }
    const queue = page.getByRole('table', { name: 'To review' });
    await expect(row(page, 'area of room (name Küche · 1.01)', queue)).toContainText(
      'Methods disagree',
    );
    // One room, one conflict: its number and its name are one row of the queue
    await expect(queue.getByRole('row', { name: /area of room/ })).toHaveCount(1);
    await shot(page, testInfo, '10-surveyor-queue', offline);
  });

  const kitchen = row(page, 'area of room (name Küche · 1.01)');
  await test.step('GP-10 step 9: settle on the drawn outline', async () => {
    await kitchen
      .getByRole('button', { name: 'area of room (name Küche · 1.01)', exact: true })
      .click();
    await page
      .getByRole('button', { name: `Keep A: 22.40 m² (${methodName('polygon_x_scale')})` })
      .click();
    await expect(kitchen).toContainText('22.40 m²');
    await expect(kitchen).toContainText('Changed in review');
    await expect(page.getByText(/Settled at 22\.40 m²/).first()).toBeVisible();
  });

  await test.step('GP-11 step 10: sign off as Ana', async () => {
    await page.getByRole('textbox', { name: 'Signing as' }).fill('Ana');
    await page.getByRole('button', { name: /^Sign off/ }).click();
    await expect(kitchen).toContainText('Verified');
    await expect(page.getByText(/Signed off by Ana/).first()).toBeVisible();
    await shot(page, testInfo, '11-signed', offline);
  });

  await test.step('GP-12 step 11: the engineer sees it verified', async () => {
    // The header has no Engineer tab any more (fe-shared, 12:50): open the drawing's engineer route directly.
    await page.goto(`${drawingUrl}/engineer`);
    await page.getByRole('textbox', { name: 'Question' }).fill(AREA);
    await page.getByRole('button', { name: 'Ask' }).click();
    const verified = turn(AREA);
    await expect(verified.getByTestId('answer-value')).toHaveText('22.40 m²');
    await expect(verified).toContainText('Verified');
    await expect(verified).toContainText(/Verified by Ana, \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/);
    await expect(verified).toBeInViewport({ ratio: 0.2 });
    await shot(page, testInfo, '12-verified', offline);
  });

  await test.step('GP-13 step 12: export the takeoff as CSV', async () => {
    await page.goto(`${drawingUrl}/surveyor`);
    const download = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Export CSV' }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe('flat-b-takeoff.csv');
    const csv = await readFile(await file.path(), 'utf8');
    const line = csv.split('\n').find((l) => l.startsWith('plans/flat-b.pdf,area:room|name=1.01,'));
    expect(line).toMatch(/,22\.401,m2,signed,30\.0,/);
    expect(line).toMatch(/,Ana,/);
  });

  await test.step("GP-52 P14: the About page holds the drawings' credits", async () => {
    await page.getByRole('contentinfo').getByRole('link', { name: 'About and credits' }).click();
    await expect(page).toHaveURL(new RegExp(`#/about\\?project=${pid}$`));
    const { credit } = (await (await page.request.get(`/api/drawings/${flatB.id}`)).json()) as {
      credit: string | null;
    };
    // The hash changes before the About screen replaces the surveyor, whose drawing list and
    // conflict lines also name flat-b: wait for the page, then read its credits list only.
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { level: 1, name: 'About Vellum' })).toBeVisible();
    const credits = main
      .locator('ul.about-credits')
      .getByRole('listitem')
      .filter({ hasText: flatB.label });
    await expect(credits).toHaveCount(1);
    await expect(credits).toContainText(
      (credit ?? 'No credit recorded for this file').replace(/^Credit:\s*/, ''),
    );
    await shot(page, testInfo, '14-about', offline);
  });

  await test.step('GP-33 GP-34 V15: the workspace history', async () => {
    // ui-bugs 10: no Workspaces pill in the header any more; the list is at #/workspaces
    await page.goto('/#/workspaces');
    await expect(page).toHaveURL(/#\/workspaces$/);
    const first = page.locator('button[aria-pressed]').first();
    await expect(first).toContainText('sample-project.zip');
    await expect(first).toHaveAttribute('aria-pressed', 'true');
    const panel = page.getByRole('region', { name: 'Selected workspace' });
    const stat = (label: string) => panel.locator('dt', { hasText: label }).locator('+ dd');
    await expect(stat('Files')).toHaveText('12');
    await expect(stat('Drawings')).toHaveText('6');
    // #131: the sample's one conflict (Küche · 1.01) is settled and signed off: nothing left to review.
    await expect(stat('To review')).toHaveText('0');
    // One sign-off per room, though #131 signs the room's twin row too (fe-shared counts by room).
    await expect(stat('Signed off')).toHaveText(/^1 of \d+$/);
    const titles = panel.locator('ol li strong');
    await expect(titles.first()).toHaveText('Uploaded sample-project.zip');
    const all = await titles.allTextContents();
    const at = (pattern: RegExp) => all.findIndex((t) => pattern.test(t));
    expect(at(/^Analysis done$/)).toBe(1);
    // #131: one conflict per room ("Küche · 1.01"); settled by a person, so no rule event is left.
    const settled = at(/^Conflict settled: area of room \(name Küche · 1\.01\)$/);
    expect(settled).toBeGreaterThan(1);
    expect(at(/^Signed off: area of room \(name Küche · 1\.01\)$/)).toBeGreaterThan(settled);
    expect(all.filter((t) => t.startsWith('Signed off: ')).length).toBe(1);
    // The chat's one question over all drawings is one entry; the engineer's ask on flat-b is the other.
    expect(all.filter((t) => t === 'Asked: How many doors are there?').length).toBe(2);
    expect(at(/^Settled by a rule: /)).toBe(-1);
    await expect(panel).toContainText('by Ana');
    // GP-36: no user, no canvas sample data (the drawing credit names the team, so not 'Hour49').
    await expect(page.locator('body')).not.toContainText(/Beatrice|harbour-block-archive/);
    await shot(page, testInfo, '13-workspaces', offline);
  });

  expect(errors, 'GP-19: console or page errors during the path').toEqual([]);
});

test('GP-20: the service is down, then back', async ({ page }) => {
  await page.route('**/api/projects', (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ status: 500, json: { detail: 'internal error', code: 'internal' } })
      : route.fallback(),
  );
  // Home lists no projects any more (IN-53): the list is on #/workspaces (no header picker since ui-bugs 10).
  await page.goto('/#/workspaces');
  const main = page.getByRole('main');
  await expect(main.getByText('internal error').first()).toBeVisible();
  await expect(main.getByText(/code: internal/).first()).toBeVisible();
  await page.unroute('**/api/projects');
  await main.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('internal error')).toHaveCount(0);
  await expect(main.getByRole('heading', { level: 1, name: 'Your workspaces' })).toBeVisible();
  await expect(
    main.getByText(/workspaces? on this server|No workspaces yet\./).first(),
  ).toBeVisible();
});

/** The sample's one conflict card (Küche · 1.01), by its heading (sentence case, CF-46). */
function kitchenCard(scope: Page | Locator): Locator {
  // `has` is matched inside each article, so it starts from the page (as in `row`).
  const page = 'page' in scope && typeof scope.page === 'function' ? scope.page() : (scope as Page);
  return scope.getByRole('article').filter({
    has: page.getByRole('heading', { name: /^area of room \(name Küche · 1\.01\)/i }),
  });
}

/** The table row whose label button is `label` (rows move between the two tables as their state changes). */
function row(page: Page, label: string | RegExp, scope: Page | Locator = page): Locator {
  // `has` is matched inside each row, so it starts from the page.
  return scope
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name: label, exact: true }) });
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
