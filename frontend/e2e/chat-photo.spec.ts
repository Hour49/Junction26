// Adding a photo from the project chat (chat.md CH-17..21, board #203) on the no-keys backend: the agent chat's
// paperclip posts a png, the status line follows the read, then a question is asked. Screenshots in
// screenshots/<project>/chat-photo-*.png.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { noKeys, sampleDone, shot, watchErrors } from './support';

/** A drawing as a png: dark outlines on white paper, as the backend's `plan_png` (tests/api/conftest.py) draws it;
 * made with the backend's Pillow, as start-backend.sh runs uv. */
function planPng(e2eDir: string): Buffer {
  const backend = path.join(e2eDir, '..', '..', 'backend');
  const code = [
    'import io, sys',
    'from PIL import Image, ImageDraw',
    "image = Image.new('RGB', (800, 400), 'white')",
    'draw = ImageDraw.Draw(image)',
    'for x in range(50, 750, 100): draw.rectangle((x, 50, x + 80, 350), outline="black", width=3)',
    'out = io.BytesIO()',
    "image.save(out, 'PNG')",
    'sys.stdout.buffer.write(out.getvalue())',
  ].join('\n');
  return execFileSync('uv', ['run', '--locked', 'python', '-c', code], { cwd: backend });
}

test('CH-17 CH-18: a photo added from the agent chat is read, then a question is asked', async ({
  page,
}, testInfo) => {
  const errors = watchErrors(page);
  const offline = await noKeys(page);
  const id = await sampleDone(page);
  const before = (
    (await (await page.request.get(`/api/projects/${id}`)).json()) as {
      files: unknown[];
    }
  ).files.length;
  await page.goto(`/#/p/${id}/chat`);
  await expect(page.getByRole('button', { name: 'Point at the plan' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add a photo' })).toBeEnabled();
  await page.getByTestId('photo-input').setInputFiles({
    name: 'phone.png',
    mimeType: 'image/png',
    buffer: planPng(testInfo.config.rootDir),
  });
  const line = page.getByRole('status').filter({ hasText: 'phone.png' });
  await expect(line).toHaveText(/^phone\.png (is read: you can ask about it|was not read)/, {
    timeout: 30_000,
  });
  await expect(page.getByRole('button', { name: 'Add a photo' })).toBeEnabled();
  const after = (
    (await (await page.request.get(`/api/projects/${id}`)).json()) as {
      files: { path: string }[];
    }
  ).files;
  expect(after).toHaveLength(before + 1);
  expect(after.at(-1)?.path).toBe('phone.png');
  await shot(page, testInfo, 'chat-photo-read', offline);
  await page.getByRole('textbox', { name: 'Question' }).fill('How many doors are there?');
  await page.getByRole('button', { name: 'Ask' }).click();
  const card = page.getByRole('article', { name: 'How many doors are there?' }).locator('.ag-card');
  await expect(card).toBeVisible({ timeout: 30_000 });
  await shot(page, testInfo, 'chat-photo-asked', offline);
  expect(errors).toEqual([]);
});
