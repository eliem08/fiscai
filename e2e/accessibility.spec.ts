import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Phase 5b — axe Accessibility Audits (Zero Serious/Critical Violations)', () => {
  const screens = [
    { name: 'Queue', query: 'queue' },
    { name: 'Review', query: 'review' },
    { name: 'Reconciliation', query: 'reconciliation' },
    { name: 'Approval', query: 'approval' },
    { name: 'Export', query: 'export' },
    { name: 'Portal', query: 'portal' },
    { name: 'Internal Metrics', query: 'metrics' },
  ];

  for (const { name, query } of screens) {
    test(`audits ${name} screen with axe-core`, async ({ page }) => {
      await page.goto(`/pilot?screen=${query}`);
      await page.waitForLoadState('networkidle');

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      // Filter for serious and critical violations
      const severeViolations = accessibilityScanResults.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical',
      );

      if (severeViolations.length > 0) {
        console.error(
          `Accessibility violations on ${name}:`,
          JSON.stringify(severeViolations, null, 2),
        );
      }

      expect(severeViolations).toEqual([]);
    });
  }
});

