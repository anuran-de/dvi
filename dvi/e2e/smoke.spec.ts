import { test, expect } from '@playwright/test';

test('landing renders and links to incidents', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /silent data change/i })).toBeVisible();
  await page.getByRole('link', { name: /see a detected incident/i }).click();
  await expect(page).toHaveURL(/incidents/);
});

test('dashboard lists incidents and opens a detail', async ({ page }) => {
  await page.goto('/incidents/');
  const firstRow = page.locator('[data-incident-link]').first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('img', { name: /blast radius/i })).toBeVisible();
});

test('respects reduced motion (content still present)', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /silent data change/i })).toBeVisible();
  await context.close();
});
