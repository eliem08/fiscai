import { expect, test } from '@playwright/test';
import { login, uploadDocument } from './helpers';

test('journey 1 — new import dossier: upload, analysis, report', async ({ page }) => {
  // 1-2. Login and open dashboard
  await login(page);
  await expect(page.getByTestId('kpi-grid')).toBeVisible();

  // 3-5. New dossier (import) with information
  await page.getByTestId('new-dossier-cta').click();
  await expect(page).toHaveURL(/dossiers\/new/);
  await page
    .getByRole('radiogroup', { name: /type de dossier/i })
    .getByText('Dossier Import', { exact: true })
    .click();
  await page.getByLabel(/titre du dossier/i).fill('E2E Import Shenzhen');
  await page.getByLabel(/client \/ entité/i).fill('E2E Client SARL');
  await page.getByRole('button', { name: /créer le dossier/i }).click();
  await expect(page).toHaveURL(/\/app\/dossiers\/dos_/);

  // 6-7. Upload commercial invoice + transport document (no packing list on purpose)
  await uploadDocument(page, 'facture-commerciale.pdf', 'Facture commerciale');
  await uploadDocument(page, 'bl-transport.pdf', 'Document de transport');

  // 8-9. Launch AI analysis; loading steps appear
  await page.getByTestId('launch-analysis').click();
  await expect(page.getByTestId('analysis-progress')).toBeVisible();

  // 10-12. Result with fiscal and customs scores
  await expect(page.getByTestId('score-cards')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('fiscal-score')).toContainText('/100');
  await expect(page.getByTestId('customs-score')).toContainText('/100');

  // 13. Missing packing list finding
  await expect(page.getByTestId('findings-list')).toContainText(/liste de colisage manquante/i);

  // 14. Checklist
  await page.getByRole('tab', { name: 'Checklist' }).click();
  await expect(page.getByTestId('checklist')).toContainText('Liste de colisage');

  // 15. Supplier / transitaire questions
  await page.getByRole('tab', { name: /questions fournisseur/i }).click();
  await expect(page.getByTestId('supplier-questions')).toContainText(/liste de colisage/i);

  // 16. Generate report
  await page.getByTestId('generate-report').click();
  await expect(page).toHaveURL(/\/app\/reports\/rpt_/);
  await expect(page.getByTestId('report-preview')).toContainText('E2E Import Shenzhen');
  await expect(page.getByTestId('report-preview')).toContainText(/synthèse exécutive/i);

  // 17-18. Reports page lists the generated report
  await page.getByRole('link', { name: /tous les rapports/i }).click();
  await expect(page.getByTestId('report-list')).toContainText('E2E Import Shenzhen');
});
