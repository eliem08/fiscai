import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('DocumentViewer & Field Correction Flow (Phase 2 UI)', () => {
  test('verifies page navigation, zoom, bbox overlay (160ms transition), and correction flow', async ({ page }) => {
    // 1. Navigate to Document Viewer
    await page.goto('/viewer');
    await expect(page.getByTestId('document-viewport')).toBeVisible();

    // 2. Page Navigation controls (◀ page X/Y ▶)
    const pageIndicator = page.getByTestId('page-indicator');
    await expect(pageIndicator).toContainText('◀ page 1/2 ▶');
    await expect(page.getByTestId('page-prev')).toBeDisabled();
    await expect(page.getByTestId('page-next')).toBeEnabled();

    // Navigate to next page
    await page.getByTestId('page-next').click();
    await expect(pageIndicator).toContainText('◀ page 2/2 ▶');
    await expect(page.getByTestId('page-next')).toBeDisabled();
    await expect(page.getByTestId('page-prev')).toBeEnabled();

    // Navigate back to page 1
    await page.getByTestId('page-prev').click();
    await expect(pageIndicator).toContainText('◀ page 1/2 ▶');

    // 3. Zoom controls
    const zoomReset = page.getByTestId('zoom-reset');
    await expect(zoomReset).toHaveText('100%');

    await page.getByTestId('zoom-in').click();
    await expect(zoomReset).toHaveText('125%');

    await page.getByTestId('zoom-in').click();
    await expect(zoomReset).toHaveText('150%');

    await zoomReset.click();
    await expect(zoomReset).toHaveText('100%');

    await page.getByTestId('zoom-out').click();
    await expect(zoomReset).toHaveText('75%');

    await zoomReset.click();
    await expect(zoomReset).toHaveText('100%');

    // 4. Bbox overlay on field focus with 160ms ease-out transition
    const iceInput = page.getByTestId('field-input-supplier_ice');
    await iceInput.focus();

    const bboxOverlay = page.getByTestId('bbox-overlay');
    await expect(bboxOverlay).toBeVisible();
    await expect(page.getByTestId('bbox-label')).toContainText('ICE Fournisseur');

    // Verify 160ms transition style
    const transitionStyle = await bboxOverlay.evaluate((el: any) => {
      return (globalThis as any).getComputedStyle(el).transition || el.style.transition;
    });
    expect(transitionStyle).toMatch(/160ms|0\.16s/);

    // Verify normalized [x0, y0, x1, y1] coordinates (supplier_ice is [0.05, 0.08, 0.35, 0.11])
    const bboxBox = await bboxOverlay.evaluate((el: any) => {
      return { left: el.style.left, top: el.style.top, width: el.style.width, height: el.style.height };
    });
    expect(bboxBox.left).toBe('5%');
    expect(bboxBox.top).toBe('8%');
    expect(bboxBox.width).toBe('30%');
    expect(bboxBox.height).toBe('3%');

    // Switch focus to invoice_number and verify bbox updates
    const invInput = page.getByTestId('field-input-invoice_number');
    await invInput.focus();
    await expect(page.getByTestId('bbox-label')).toContainText('Numéro de facture');

    const invBbox = await bboxOverlay.evaluate((el: any) => {
      return { left: el.style.left, top: el.style.top, width: el.style.width, height: el.style.height };
    });
    expect(invBbox.left).toBe('5%');
    expect(invBbox.top).toBe('14%');
    expect(invBbox.width).toBe('33%');

    // 5. Field correction flow
    // Notice unconfirmed field indicator (8px pink dot)
    const iceContainer = page.getByTestId('field-container-supplier_ice');
    await expect(iceContainer).toContainText('à confirmer');
    await expect(iceContainer.getByTestId('unconfirmed-marker')).toBeVisible();

    // Accountant edits the field
    await iceInput.fill('001234567899999');
    await iceInput.press('Enter');

    // Enter confirms field
    await expect(iceContainer).toContainText('Confirmé');

    // Edit another field
    const ttcInput = page.getByTestId('field-input-total_ttc');
    await ttcInput.focus();
    await ttcInput.fill('1250.00');

    // Save changes
    const saveBtn = page.getByTestId('save-corrections-btn');
    await saveBtn.click();

    // Verify confirmation banner
    const successBanner = page.getByTestId('save-success-banner');
    await expect(successBanner).toBeVisible();
    await expect(successBanner).toContainText('Correction enregistrée et rattachée au dossier d’audit.');

    // 6. Capture high-resolution screenshot for Phase 2 report
    const screenshotDir = path.resolve(process.cwd(), 'docs', 'screenshots');
    const screenshotPath = path.join(screenshotDir, 'document-viewer.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    expect(screenshotPath).toBeDefined();
  });

  test('respects prefers-reduced-motion: reduce', async ({ page }) => {
    // Emulate reduced motion
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/viewer');

    const iceInput = page.getByTestId('field-input-supplier_ice');
    await iceInput.focus();

    const bboxOverlay = page.getByTestId('bbox-overlay');
    await expect(bboxOverlay).toBeVisible();

    // In reduced motion, transition is disabled by motion-reduce:transition-none
    const hasReducedMotionClass = await bboxOverlay.evaluate((el) =>
      el.classList.contains('motion-reduce:transition-none')
    );
    expect(hasReducedMotionClass).toBe(true);
  });
});
