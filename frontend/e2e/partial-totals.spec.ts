// CH-49 (chat.md): a room total that may leave rooms out has a "May be partial" tag beside its value. The sample
// answers for real; the one change is the #350 fields on the first part, with the sentence the backend then puts in
// its explanation and reason (answer.py partial_text), which the no-keys sample's vector sheets never make partial.
import { expect, test, type Route } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const PARTIAL = { partial: true, rooms_counted: 7, rooms_missing: ['Sauna', 'WC 2'] };
const TIP = 'May be partial: sums 7 rooms; 2 not in it';
const SAID =
  'This is the sum of the 7 rooms the reader found; rooms it missed are not in it. Not in it: Sauna, WC 2.';

type View = Record<string, unknown> & { level?: object | null; check?: object | null };
type Part = { answer: View };

/** As the backend sends a partial total: the fields, and its sentence wherever the row's reason comes from. */
function partialAnswer(a: View): View {
  return {
    ...a,
    ...PARTIAL,
    explanation: SAID,
    level: { ...(a.level ?? { level: 'low' }), text: SAID },
    check: a.check ? { ...a.check, reason: SAID } : a.check,
  };
}
type Answer = { parts: Part[] };

/** The real response, with the first part of each project answer partial. */
async function partial(route: Route) {
  const response = await route.fetch();
  const body = (await response.json()) as Answer & { answers?: Answer[] };
  for (const ask of body.answers ?? [body]) {
    const first = ask.parts[0];
    if (first) first.answer = partialAnswer(first.answer);
  }
  await route.fulfill({ response, json: body });
}

/** The same for the agent chat's step stream: its last `answer` event carries the turn and its answers. */
async function partialStream(route: Route) {
  const response = await route.fetch();
  const frames = (await response.text()).split('\n\n').map((frame) => {
    if (!frame.startsWith('event: answer\n')) return frame;
    const turn = JSON.parse(frame.slice(frame.indexOf('data: ') + 6)) as { answers: Answer[] };
    for (const ask of turn.answers) {
      const first = ask.parts[0];
      if (first) first.answer = partialAnswer(first.answer);
    }
    return `event: answer\ndata: ${JSON.stringify(turn)}`;
  });
  await route.fulfill({ response, body: frames.join('\n\n') });
}

test('CH-49 a partial room total has one tag beside its value; the missing rooms are named once', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const id = await sampleDone(page);
  await page.route(`**/api/projects/${id}/ask`, partial);
  await page.route(`**/api/projects/${id}/chat`, partial);
  await page.route(`**/api/projects/${id}/chat/stream`, partialStream);
  await page.goto(`/#/p/${id}/chat?ask=${encodeURIComponent('How many rooms are there?')}`);
  const tag = page.getByRole('note', { name: TIP });
  await expect(tag).toHaveCount(1, { timeout: 30_000 });
  await expect(tag).toHaveText('May be partial');
  await expect(tag).toHaveAttribute('title', TIP);
  await tag.scrollIntoViewIfNeeded();
  await expect(tag).toBeVisible();
  const box = await tag.boundingBox();
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(page.viewportSize()?.width ?? 0);
  const row = page
    .getByRole('list', { name: 'Per drawing' })
    .getByRole('listitem')
    .filter({ has: tag });
  const text = (await row.textContent()) ?? '';
  expect(text.split('Sauna').length - 1).toBe(1);
  expect(text.split('WC 2').length - 1).toBe(1);
  await shot(page, testInfo, 'chat-partial-total', await noKeys(page));
  expect(errors).toEqual([]);
});
