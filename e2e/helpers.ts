import { expect, type Page } from '@playwright/test';

export async function login(page: Page, email = 'demo@fiscai.ma', password = 'Demo1234!') {
  await page.goto('/login');
  await page.getByLabel(/adresse e-mail/i).fill(email);
  await page.getByLabel(/mot de passe/i).fill(password);
  await page.getByRole('button', { name: /se connecter/i }).click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
}

export async function createDossier(
  page: Page,
  title: string,
  type: 'Dossier Import' | 'Dossier Export' | 'Dossier Fiscal / TVA' = 'Dossier Import',
) {
  await page.goto('/app/dossiers/new');
  await page
    .getByRole('radiogroup', { name: /type de dossier/i })
    .getByText(type, { exact: true })
    .click();
  await page.getByLabel(/titre du dossier/i).fill(title);
  await page.getByLabel(/client \/ entité/i).fill('Client E2E SARL');
  await page.getByRole('button', { name: /créer le dossier/i }).click();
  await expect(page).toHaveURL(/\/app\/dossiers\/dos_/);
}

export async function uploadDocument(page: Page, fileName: string, docTypeLabel: string) {
  await page.getByLabel(/type de document/i).selectOption({ label: docTypeLabel });
  await page
    .getByLabel(/sélectionner un document/i)
    .setInputFiles({
      name: fileName,
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 mock'),
    });
  await expect(page.getByTestId('document-list')).toContainText(fileName);
}
