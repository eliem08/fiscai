import { expect, test } from '@playwright/test';
import { login } from './helpers';

test('journey 3 — alerts workflow: filter, review, dossier reflects issue', async ({ page }) => {
  // 1. Open the alerts center
  await login(page);
  await page.getByRole('link', { name: /alertes/i }).click();
  await expect(page).toHaveURL(/alerts/);
  await expect(page.getByTestId('alert-list')).toBeVisible();

  // 2. Filter by critical alerts
  await page.getByLabel(/sévérité/i).selectOption('critical');
  const cards = page.getByTestId('alert-card');
  // Seed data contains exactly one critical alert; wait for the filter to apply.
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toHaveAttribute('data-severity', 'critical');

  // 3-5. Open the missing-document alert and mark it in review
  const missingDoc = cards.filter({ hasText: 'Liste de colisage manquante' }).first();
  await expect(missingDoc).toBeVisible();
  await missingDoc.getByRole('button', { name: /passer en revue/i }).click();
  await expect(page.getByText(/mise à jour \(en cours de revue\)/i)).toBeVisible();

  // 6. Dossier status reflects the active issue
  await page.getByRole('link', { name: 'Dossiers', exact: true }).click();
  await page.getByLabel('Recherche').fill('composants');
  await expect(page.getByTestId('dossier-card').first()).toContainText('Problème actif');
});
