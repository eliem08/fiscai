import { expect, test } from '@playwright/test';
import { createDossier, login } from './helpers';

test('journey 5 — validation and error handling', async ({ page }) => {
  await login(page);

  // 1-2. Dossier without a title -> validation error
  await page.goto('/app/dossiers/new');
  await page
    .getByRole('radiogroup', { name: /type de dossier/i })
    .getByText('Dossier Import', { exact: true })
    .click();
  await page.getByLabel(/client \/ entité/i).fill('Client E2E');
  await page.getByRole('button', { name: /créer le dossier/i }).click();
  await expect(page.getByTestId('title-error')).toContainText(/obligatoire/i);

  // Create a valid dossier to continue
  await createDossier(page, 'E2E Validation Import');

  // 3-4. Unsupported file type -> file type error
  await page.getByLabel(/type de document/i).selectOption({ label: 'Autre document' });
  await page
    .getByLabel(/sélectionner un document/i)
    .setInputFiles({
      name: 'script.exe',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('MZ'),
    });
  await expect(page.getByTestId('upload-error')).toContainText(/non supporté/i);

  // 5-6. Analysis without required documents -> warning, allow partial analysis
  await page.getByTestId('launch-analysis').click();
  await expect(page.getByRole('dialog', { name: /documents requis manquants/i })).toBeVisible();
  await page.getByTestId('confirm-partial-analysis').click();

  // 7. Low-confidence / partial result is clearly flagged
  await expect(page.getByTestId('score-cards')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('partial-banner')).toBeVisible();
  await expect(page.getByTestId('low-confidence-banner')).toBeVisible();
});

test('analysis failure path shows a retryable error state', async ({ page }) => {
  await login(page);
  await createDossier(page, '[fail-analysis] E2E Panne moteur');
  await page.getByTestId('launch-analysis').click();
  await page.getByTestId('confirm-partial-analysis').click();
  await expect(page.getByTestId('error-state')).toContainText(/analyse ia a échoué/i, {
    timeout: 20_000,
  });
  await expect(page.getByRole('button', { name: /réessayer/i })).toBeVisible();
});
