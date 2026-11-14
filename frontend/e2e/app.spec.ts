import { expect, test } from '@playwright/test';

test('loads the app', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Countersign');
  await expect(page.getByRole('heading', { name: 'Countersign' })).toBeVisible();
});
