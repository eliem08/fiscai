import { describe, expect, it } from 'vitest';
import { generateAlertsFromFindings, severityForFinding } from './alertRules';
import { computeRiskScores } from './riskScoring';
import { extractDocument } from './extraction';
import type { DocumentType } from '@/types/models';

const ctx = { organizationId: 'org_demo', dossierId: 'dos_x' };

function findingsFor(documentTypes: DocumentType[], invoiceName = 'facture.pdf') {
  const extractions = documentTypes.map((t, i) =>
    extractDocument({
      id: `d${i}`,
      name: t === 'commercial_invoice' ? invoiceName : `${t}.pdf`,
      type: t,
    }),
  );
  return computeRiskScores({ dossierType: 'import', documentTypes, extractions }).findings;
}

describe('alert generation rules', () => {
  it('creates a critical alert for a missing packing list', () => {
    const findings = findingsFor([
      'commercial_invoice',
      'transport_document',
      'certificate_origin',
    ]);
    const alerts = generateAlertsFromFindings(findings, ctx);
    const packing = alerts.find((a) => a.title.includes('colisage'));
    expect(packing).toBeDefined();
    expect(packing!.severity).toBe('critical');
    expect(packing!.status).toBe('open');
    expect(packing!.dossierId).toBe('dos_x');
  });

  it('creates a high alert for HS-code uncertainty', () => {
    const types: DocumentType[] = [
      'commercial_invoice',
      'packing_list',
      'transport_document',
      'certificate_origin',
      'customs_declaration',
    ];
    const extractions = [
      ...types
        .slice(0, 4)
        .map((t, i) => extractDocument({ id: `d${i}`, name: `${t}.pdf`, type: t })),
      extractDocument({ id: 'dum', name: 'dum-sans-sh.pdf', type: 'customs_declaration' }),
    ];
    const findings = computeRiskScores({
      dossierType: 'import',
      documentTypes: types,
      extractions,
    }).findings;
    const alerts = generateAlertsFromFindings(findings, ctx);
    expect(alerts.find((a) => a.title.includes('Code SH'))?.severity).toBe('high');
  });

  it('creates a medium alert for a VAT mismatch', () => {
    const findings = findingsFor(
      ['commercial_invoice', 'packing_list', 'transport_document', 'certificate_origin'],
      'facture-tva-erreur.pdf',
    );
    const alerts = generateAlertsFromFindings(findings, ctx);
    expect(alerts.find((a) => a.title.includes('TVA'))?.severity).toBe('medium');
  });

  it('creates a low alert for missing optional certificate of origin', () => {
    const findings = findingsFor(['commercial_invoice', 'packing_list', 'transport_document']);
    const alerts = generateAlertsFromFindings(findings, ctx);
    expect(alerts.find((a) => a.title.includes('origine'))?.severity).toBe('low');
  });

  it('falls back to the finding severity for unknown codes', () => {
    expect(
      severityForFinding({
        id: 'x',
        domain: 'general',
        code: 'UNKNOWN_CODE',
        severity: 'medium',
        title: 't',
        detail: 'd',
        recommendedAction: 'a',
      }),
    ).toBe('medium');
  });
});
