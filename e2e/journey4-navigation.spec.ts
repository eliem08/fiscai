import { expect, test } from '@playwright/test';
import { login } from './helpers';

test('journey 4 — dashboard navigation without errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  // 1-2. Login, KPI cards visible
  await login(page);
  await expect(page.getByTestId('kpi-grid')).toBeVisible();

  // 3-4. Open a recent dossier -> analysis page
  await page.getByTestId('dossier-card').first().click();
  await expect(page).toHaveURL(/\/app\/dossiers\/dos_/);

  // 5. Back to dashboard
  await page.getByRole('link', { name: /tableau de bord/i }).click();
  await expect(page.getByTestId('kpi-grid')).toBeVisible();

  // 6. Reports
  await page.getByRole('link', { name: 'Rapports', exact: true }).click();
  await expect(page).toHaveURL(/reports/);

  // 7. Settings
  await page.getByRole('link', { name: /paramètres/i }).click();
  await expect(page).toHaveURL(/settings/);
  await expect(page.getByTestId('privacy-notice')).toBeVisible();

  // Extra coverage: documents, agents, pricing (public)
  await page.getByRole('link', { name: 'Documents', exact: true }).click();
  await expect(page).toHaveURL(/documents/);
  await page.getByRole('link', { name: /agents ia/i }).click();
  await expect(page).toHaveURL(/agents/);

  // 8. No runtime errors anywhere on the way
  expect(errors).toEqual([]);
});

test('unauthenticated users are redirected to login (auth guard)', async ({ page }) => {
  await page.goto('/app/dashboard');
  await expect(page).toHaveURL(/\/login/);
});

test('unknown routes show the not-found page, not a crash', async ({ page }) => {
  await page.goto('/nulle-part');
  await expect(page.getByText(/page introuvable/i)).toBeVisible();
});
