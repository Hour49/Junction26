// CH-49 (chat.md): a room total that may leave rooms out says so under its value. The sample answers for real; the
// one change is the #350 fields on the first part, which the no-keys sample's vector sheets never make partial.
import { expect, test, type Route } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

const PARTIAL = { partial: true, rooms_counted: 7, rooms_missing: ['Sauna', 'WC 2'] };
const LINE = 'May be partial: sums 7 rooms the reader found; missing from it: Sauna, WC 2.';

type Part = { answer: Record<string, unknown> };
type Answer = { parts: Part[] };

/** The real response, with the first part of each project answer partial. */
async function partial(route: Route) {
  const response = await route.fetch();
  const body = (await response.json()) as Answer & { answers?: Answer[] };
  for (const ask of body.answers ?? [body]) {
    const first = ask.parts[0];
    if (first) first.answer = { ...first.answer, ...PARTIAL };
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
      if (first) first.answer = { ...first.answer, ...PARTIAL };
    }
    return `event: answer\ndata: ${JSON.stringify(turn)}`;
  });
  await route.fulfill({ response, body: frames.join('\n\n') });
}

test('CH-49 a partial room total shows one plain line under its value', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const id = await sampleDone(page);
  await page.route(`**/api/projects/${id}/ask`, partial);
  await page.route(`**/api/projects/${id}/chat`, partial);
  await page.route(`**/api/projects/${id}/chat/stream`, partialStream);
  await page.goto(`/#/p/${id}/chat?ask=${encodeURIComponent('How many rooms are there?')}`);
  const line = page.getByText(LINE);
  await expect(line).toHaveCount(1, { timeout: 30_000 });
  await line.scrollIntoViewIfNeeded();
  await expect(line).toBeVisible();
  const box = await line.boundingBox();
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(page.viewportSize()?.width ?? 0);
  await shot(page, testInfo, 'chat-partial-total', await noKeys(page));
  expect(errors).toEqual([]);
});
