// The surveyor's e2e criteria the golden path does not walk (surveyor.md SV-47, SV-48: reject and restore a door,
// undo a sign-off), on the live no-keys backend.
import { expect, test } from '@playwright/test';
import { noKeys, openSurveyor, shot, watchErrors } from './support';

test('SV-47, SV-48: reject and restore a door, sign off and undo', async ({ page }, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  await openSurveyor(page);
  await expect(page.getByRole('table', { name: 'To review' })).toContainText(
    'area of room (name Küche · 1.01)',
  );
  await shot(page, testInfo, 'surveyor-1-open', offline);

  const door = page
    .getByRole('row')
    .filter({ has: page.getByRole('button', { name: 'door count', exact: true }) });
  await door.getByRole('button', { name: 'door count', exact: true }).click();
  await expect(door.getByRole('cell').first()).toHaveText('2');
  const marks = page.getByRole('list', { name: 'Marks' });

  await marks.getByRole('listitem').nth(1).getByRole('button', { name: 'Reject' }).click();
  await expect(door.getByRole('cell').first()).toContainText('1');
  await expect(door).toContainText('Changed in review');
  await shot(page, testInfo, 'surveyor-2-rejected', offline);

  await marks.getByRole('listitem').nth(1).getByRole('button', { name: 'Restore' }).click();
  await expect(door.getByRole('cell').first()).toHaveText('2');

  await page.getByRole('textbox', { name: 'Signing as' }).fill('Ana');
  await page.getByRole('button', { name: 'Sign off 2' }).click();
  await expect(door).toContainText('Verified');
  await page.getByRole('button', { name: 'Undo sign-off' }).click();
  await expect(door).not.toContainText('Verified');
  await expect(page.getByRole('button', { name: 'Sign off 2' })).toBeVisible();
  await shot(page, testInfo, 'surveyor-3-undone', offline);

  expect(errors, 'console or page errors').toEqual([]);
});

// SV-55 (QA R4-c-1): `.sv-screen button` overrode the viewer's badges, so counted marks showed as grey pills.
test('SV-55: the viewer badges keep their look on the surveyor route', async ({
  page,
}, testInfo) => {
  const offline = await noKeys(page);
  await openSurveyor(page);
  const badges = page.locator('.vw-badge');
  await expect(badges.first()).toBeVisible();
  await badges.first().scrollIntoViewIfNeeded();
  await shot(page, testInfo, 'surveyor-4-badges', offline);
  // each badge against the viewer's own look (viewer.css), with the tokens resolved in this page
  const wrong = await page.evaluate(() => {
    const probe = document.body.appendChild(document.createElement('i'));
    const token = (name: string) => {
      probe.style.backgroundColor = `var(${name})`;
      return getComputedStyle(probe).backgroundColor;
    };
    const filled = token('--v-accent');
    const open = token('--v-surface');
    probe.remove();
    return [
      ...document.querySelectorAll<HTMLElement>(
        '.vw-badge:not(.vw-hot):not([aria-pressed="true"])',
      ),
    ]
      .map((b) => {
        const s = getComputedStyle(b);
        const isOpen = b.classList.contains('vw-badge--open');
        const ok =
          s.backgroundColor === (isOpen ? open : filled) &&
          s.borderTopStyle ===
            (isOpen ? 'dashed' : b.classList.contains('vw-badge--rejected') ? 'dotted' : 'solid') &&
          s.borderRadius === '12px';
        return ok
          ? ''
          : `${b.className}: ${s.backgroundColor} ${s.borderTopStyle} ${s.borderRadius}`;
      })
      .filter(Boolean);
  });
  expect(wrong).toEqual([]);
});
