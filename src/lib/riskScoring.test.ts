import { describe, expect, it } from 'vitest';
import { computeRiskScores, levelForScore, type ScoringInput } from './riskScoring';
import { extractDocument } from './extraction';
import type { DocumentType, ExtractionResult } from '@/types/models';

function extractionsFor(names: Partial<Record<DocumentType, string>>): ExtractionResult[] {
  return Object.entries(names).map(([type, name], i) =>
    extractDocument({ id: `d${i}`, name, type: type as DocumentType }),
  );
}

const FULL_DOCS: DocumentType[] = [
  'commercial_invoice',
  'packing_list',
  'transport_document',
  'certificate_origin',
];

function cleanImportInput(): ScoringInput {
  return {
    dossierType: 'import',
    documentTypes: FULL_DOCS,
    extractions: extractionsFor({
      commercial_invoice: 'facture.pdf',
      packing_list: 'colisage.pdf',
      transport_document: 'bl.pdf',
      certificate_origin: 'co.pdf',
    }),
  };
}

describe('levelForScore', () => {
  it('maps thresholds to levels', () => {
    expect(levelForScore(0)).toBe('low');
    expect(levelForScore(24)).toBe('low');
    expect(levelForScore(25)).toBe('medium');
    expect(levelForScore(50)).toBe('high');
    expect(levelForScore(75)).toBe('critical');
    expect(levelForScore(100)).toBe('critical');
  });
});

describe('computeRiskScores', () => {
  it('scores a complete, consistent import dossier as low risk', () => {
    const scores = computeRiskScores(cleanImportInput());
    expect(scores.level).toBe('low');
    expect(scores.overall).toBeLessThan(25);
    expect(scores.expertReviewRequired).toBe(false);
    expect(scores.findings).toHaveLength(0);
  });

  it('scores a dossier with a single VAT mismatch as medium risk (fiscal)', () => {
    const input: ScoringInput = {
      dossierType: 'fiscal',
      documentTypes: ['commercial_invoice', 'vat_declaration'],
      extractions: extractionsFor({
        commercial_invoice: 'facture-tva-erreur.pdf',
        vat_declaration: 'tva.pdf',
      }),
    };
    const scores = computeRiskScores(input);
    expect(scores.findings.map((f) => f.code)).toContain('VAT_MISMATCH');
    expect(scores.level).toBe('medium');
  });

  it('scores an import dossier with several customs problems as high risk', () => {
    const input: ScoringInput = {
      dossierType: 'import',
      documentTypes: ['commercial_invoice', 'customs_declaration'],
      extractions: extractionsFor({
        commercial_invoice: 'facture-vague.pdf',
        customs_declaration: 'dum-sans-sh.pdf',
      }),
    };
    const scores = computeRiskScores(input);
    expect(scores.level).toBe('high');
    expect(scores.expertReviewRequired).toBe(true);
  });

  it('scores an empty, incoherent dossier as critical risk', () => {
    const input: ScoringInput = {
      dossierType: 'import',
      documentTypes: ['customs_declaration'],
      extractions: extractionsFor({
        commercial_invoice: 'facture-flou-tva-erreur-vague-sans-fournisseur.pdf',
        customs_declaration: 'dum-sans-sh.pdf',
      }),
    };
    const scores = computeRiskScores(input);
    expect(scores.customs).toBeGreaterThanOrEqual(75);
    expect(scores.level).toBe('critical');
    expect(scores.expertReviewRequired).toBe(true);
  });

  it('missing packing list increases customs risk with a critical finding', () => {
    const base = computeRiskScores(cleanImportInput());
    const without = computeRiskScores({
      ...cleanImportInput(),
      documentTypes: FULL_DOCS.filter((t) => t !== 'packing_list'),
    });
    expect(without.customs).toBeGreaterThan(base.customs);
    const finding = without.findings.find((f) => f.code === 'MISSING_PACKING_LIST');
    expect(finding).toBeDefined();
    expect(finding!.severity).toBe('critical');
    expect(finding!.domain).toBe('customs');
  });

  it('VAT mismatch increases fiscal risk', () => {
    const base = computeRiskScores(cleanImportInput());
    const input = cleanImportInput();
    input.extractions = extractionsFor({
      commercial_invoice: 'facture-tva-erreur.pdf',
      packing_list: 'colisage.pdf',
      transport_document: 'bl.pdf',
      certificate_origin: 'co.pdf',
    });
    const scores = computeRiskScores(input);
    expect(scores.fiscal).toBeGreaterThan(base.fiscal);
    expect(scores.findings.map((f) => f.code)).toContain('VAT_MISMATCH');
  });

  it('missing supplier identity increases both fiscal and customs risk', () => {
    const base = computeRiskScores(cleanImportInput());
    const input = cleanImportInput();
    input.extractions = extractionsFor({
      commercial_invoice: 'facture-sans-fournisseur.pdf',
      packing_list: 'colisage.pdf',
      transport_document: 'bl.pdf',
      certificate_origin: 'co.pdf',
    });
    const scores = computeRiskScores(input);
    expect(scores.fiscal).toBeGreaterThan(base.fiscal);
    expect(scores.customs).toBeGreaterThan(base.customs);
    expect(scores.findings.map((f) => f.code)).toContain('MISSING_SUPPLIER_IDENTITY');
  });

  it('HS-code uncertainty increases customs risk', () => {
    const input: ScoringInput = {
      dossierType: 'import',
      documentTypes: [...FULL_DOCS, 'customs_declaration'],
      extractions: [
        ...cleanImportInput().extractions,
        extractDocument({ id: 'dum', name: 'dum-sans-sh.pdf', type: 'customs_declaration' }),
      ],
    };
    const scores = computeRiskScores(input);
    const base = computeRiskScores(cleanImportInput());
    expect(scores.customs).toBeGreaterThan(base.customs);
    expect(scores.findings.map((f) => f.code)).toContain('HS_CODE_UNCERTAIN');
  });

  it('vague product description increases customs risk', () => {
    const input = cleanImportInput();
    input.extractions = extractionsFor({
      commercial_invoice: 'facture-vague.pdf',
      packing_list: 'colisage.pdf',
      transport_document: 'bl.pdf',
      certificate_origin: 'co.pdf',
    });
    const scores = computeRiskScores(input);
    const base = computeRiskScores(cleanImportInput());
    expect(scores.customs).toBeGreaterThan(base.customs);
    expect(scores.findings.map((f) => f.code)).toContain('VAGUE_DESCRIPTION');
  });

  it('missing certificate of origin creates a low-severity warning', () => {
    const input = cleanImportInput();
    input.documentTypes = FULL_DOCS.filter((t) => t !== 'certificate_origin');
    const scores = computeRiskScores(input);
    const finding = scores.findings.find((f) => f.code === 'MISSING_CERTIFICATE_ORIGIN');
    expect(finding).toBeDefined();
    expect(finding!.severity).toBe('low');
  });

  it('requires expert review when risk is high or critical', () => {
    const high = computeRiskScores({
      dossierType: 'import',
      documentTypes: ['commercial_invoice'],
      extractions: extractionsFor({ commercial_invoice: 'facture-vague-sans-fournisseur.pdf' }),
    });
    expect(high.level === 'high' || high.level === 'critical').toBe(true);
    expect(high.expertReviewRequired).toBe(true);
  });

  it('fiscal dossiers do not raise customs-only findings', () => {
    const scores = computeRiskScores({
      dossierType: 'fiscal',
      documentTypes: ['commercial_invoice', 'vat_declaration'],
      extractions: extractionsFor({
        commercial_invoice: 'facture.pdf',
        vat_declaration: 'tva.pdf',
      }),
    });
    const codes = scores.findings.map((f) => f.code);
    expect(codes).not.toContain('MISSING_PACKING_LIST');
    expect(codes).not.toContain('HS_CODE_UNCERTAIN');
  });
});
