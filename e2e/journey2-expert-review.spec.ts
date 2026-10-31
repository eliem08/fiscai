import { expect, test } from '@playwright/test';
import { login } from './helpers';

test('journey 2 — expert review workflow with audit trail', async ({ page }) => {
  // 1. Expert opens the review queue
  await login(page, 'expert@fiscai.ma');
  await page.getByRole('link', { name: /revue experte/i }).click();
  await expect(page).toHaveURL(/expert-review/);

  // 2. Select the dossier awaiting review (seeded dos_001)
  const awaiting = page.getByTestId('awaiting-list');
  await expect(awaiting).toContainText('Import composants électroniques');
  await awaiting.getByRole('button').first().click();

  // 3. AI findings summary appears in the form
  await expect(page.getByTestId('review-form')).toBeVisible();

  // 4-6. Choose "Correction required", add a comment, save
  await page.getByRole('radio', { name: /correction requise/i }).check();
  await page
    .getByLabel(/commentaire expert/i)
    .fill('Code SH à confirmer par le transitaire avant dépôt BADR.');
  await page.getByTestId('submit-review').click();
  await expect(page.getByText(/revue enregistrée/i)).toBeVisible();

  // 7. Dossier status updated (correction_required -> "Problème actif")
  await page.getByRole('link', { name: 'Dossiers', exact: true }).click();
  await page.getByLabel('Recherche').fill('composants');
  const card = page.getByTestId('dossier-card').first();
  await expect(card).toContainText('Problème actif');

  // 8. Audit log entry created (visible to admin)
  await page.getByRole('button', { name: /déconnexion/i }).click();
  await login(page, 'admin@fiscai.ma');
  await page.getByRole('link', { name: /journal d’audit/i }).click();
  await expect(page.getByTestId('audit-table')).toContainText('expert_review.submitted');
});
