import { test, expect } from '@playwright/test';

test.describe('Phase 5b — Pilot End-to-End Monthly File Journey', () => {
  test('executes a complete monthly file from client creation to Sage export and evidence pack', async ({
    page,
  }) => {
    // Navigate to the Pilot Journey Orchestrator
    await page.goto('/pilot?screen=journey');
    await page.waitForLoadState('networkidle');

    await expect(page.getByTestId('pilot-journey-container')).toBeVisible();

    // 1. Step 1: Create client entity (SARL, ICE 15 digits)
    await expect(page.getByTestId('step-client-creation')).toBeVisible();
    await expect(page.locator('#company-ice')).toHaveValue('001523456000089');
    await expect(page.locator('#company-form')).toHaveValue('SARL');
    await page.getByTestId('btn-create-client').click();

    // 2. Step 2: Import CGNC chart of accounts
    await expect(page.getByTestId('step-chart-import')).toBeVisible();
    await expect(page.getByText('CGNC 1989')).toBeVisible();
    await page.getByTestId('btn-import-chart').click();

    // 3. Step 3: Open period (2026-10)
    await expect(page.getByTestId('step-open-period')).toBeVisible();
    await expect(page.locator('#period-code')).toHaveValue('2026-10 (Octobre 2026)');
    await page.getByTestId('btn-open-period').click();

    // 4. Step 4: Upload invoices + bank statement
    await expect(page.getByTestId('step-upload-documents')).toBeVisible();
    await expect(page.getByText('FAC-2026-0891_Fournisseur_Papeterie.pdf')).toBeVisible();
    await expect(page.getByText('Releve_Bancaire_Attijariwafa_Octobre2026.pdf')).toBeVisible();
    await page.getByTestId('btn-upload-files').click();

    // 5. Step 5: Review and correct a field in DocumentViewer
    await expect(page.getByTestId('step-review-correction')).toBeVisible();
    await expect(page.getByTestId('mock-bbox-overlay')).toBeVisible();
    const iceInput = page.getByTestId('input-correct-ice');
    await iceInput.fill('001523456000099');
    await page.getByTestId('btn-confirm-field').click();
    await expect(page.getByTestId('btn-confirm-field')).toContainText('Champ confirmé ✓');
    await page.getByTestId('btn-proceed-issues').click();

    // 6. Step 6: Resolve & acknowledge review issues
    await expect(page.getByTestId('step-resolve-issues')).toBeVisible();
    await expect(page.getByText('DOC_NOTE_MISSING')).toBeVisible();
    await page.getByTestId('btn-acknowledge-issue').click();
    await expect(page.getByTestId('btn-acknowledge-issue')).toContainText('Anomalie acquittée ✓');
    await page.getByTestId('btn-proceed-reconciliation').click();

    // 7. Step 7: Accept bank reconciliation matches
    await expect(page.getByTestId('step-reconciliation')).toBeVisible();
    await expect(page.getByText('-12 000,00 MAD')).toBeVisible();
    await page.getByTestId('btn-accept-match').click();
    await expect(page.getByTestId('btn-accept-match')).toContainText('Rapprochement validé ✓');
    await page.getByTestId('btn-proceed-staff-request').click();

    // 8. Step 8: Request approval as staff
    await expect(page.getByTestId('step-staff-request')).toBeVisible();
    await page.getByTestId('btn-request-approval').click();

    // 9. Step 9: Approve as accountant with MFA
    await expect(page.getByTestId('step-accountant-approval')).toBeVisible();
    await expect(page.getByText('N° Ordre : OEC-45678')).toBeVisible();
    await expect(page.getByText('Mehdi Bennani (Expert-Comptable Diplômé)')).toBeVisible();
    const mfaInput = page.getByTestId('input-mfa-code');
    await mfaInput.fill('987654');
    await page.getByTestId('btn-approve-dossier').click();

    // 10. Step 10: Export Sage CSV & Evidence pack
    await expect(page.getByTestId('step-export')).toBeVisible();
    await page.getByTestId('btn-generate-sage-csv').click();
    await expect(page.getByTestId('export-success-banner')).toBeVisible();
    await expect(page.getByTestId('btn-download-evidence-pack')).toBeEnabled();

    // 11. Step 11: Verify Internal Operational Metrics (Review Effort & Cost)
    await page.goto('/pilot?screen=metrics&role=owner');
    await expect(page.getByText('Indicateurs internes — Effort de révision & coûts')).toBeVisible();
    await expect(page.getByTestId('metric-review-time')).toHaveText('3 min 05 s');
    await expect(page.getByTestId('metric-corrections')).toHaveText('1 champ(s)');
    await expect(page.getByTestId('metric-issues-resolved')).toHaveText('1');
    await expect(page.getByTestId('metric-cost-per-file')).toHaveText('0.0420 MAD');
    await expect(page.getByText('Société Atlas Négoce SARL')).toBeVisible();

    // Capture screenshot of internal metrics screen with real populated numbers
    await page.screenshot({ path: 'docs/screenshots/internal-metrics.png', fullPage: true });

    // Verify RBAC: staff cannot access internal metrics (access denied)
    await page.goto('/pilot?screen=metrics&role=staff');
    await expect(page.getByText('Accès restreint')).toBeVisible();
  });
});
