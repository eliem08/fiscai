import { describe, expect, it } from 'vitest';
import { buildChecklist, buildSupplierQuestions } from './checklist';
import { computeRiskScores } from './riskScoring';
import { extractDocument } from './extraction';
import type { DocumentType } from '@/types/models';

function scoresFor(documentTypes: DocumentType[], invoiceName = 'facture.pdf') {
  const extractions = documentTypes.map((t, i) =>
    extractDocument({
      id: `d${i}`,
      name: t === 'commercial_invoice' ? invoiceName : `${t}.pdf`,
      type: t,
    }),
  );
  return computeRiskScores({ dossierType: 'import', documentTypes, extractions });
}

const FULL: DocumentType[] = [
  'commercial_invoice',
  'packing_list',
  'transport_document',
  'certificate_origin',
];

describe('buildChecklist', () => {
  it('marks all required documents as passed when present and consistent', () => {
    const scores = scoresFor(FULL);
    const items = buildChecklist({ dossierType: 'import', documentTypes: FULL, scores });
    const docItems = items.filter((i) =>
      ['Facture commerciale', 'Liste de colisage'].includes(i.label),
    );
    expect(docItems.every((i) => i.status === 'passed')).toBe(true);
    expect(items.find((i) => i.label.includes('Cohérence TVA'))?.status).toBe('passed');
  });

  it('marks VAT check as failed on mismatch with a recommended action', () => {
    const scores = scoresFor(FULL, 'facture-tva-erreur.pdf');
    const items = buildChecklist({ dossierType: 'import', documentTypes: FULL, scores });
    const vat = items.find((i) => i.label.includes('Cohérence TVA'));
    expect(vat?.status).toBe('failed');
    expect(vat?.recommendedAction).toBeTruthy();
  });

  it('marks HS-code check as needs_review when uncertain', () => {
    const types: DocumentType[] = [...FULL, 'customs_declaration'];
    const extractions = [
      ...FULL.map((t, i) => extractDocument({ id: `d${i}`, name: `${t}.pdf`, type: t })),
      extractDocument({ id: 'dum', name: 'dum-sans-sh.pdf', type: 'customs_declaration' }),
    ];
    const scores = computeRiskScores({ dossierType: 'import', documentTypes: types, extractions });
    const items = buildChecklist({ dossierType: 'import', documentTypes: types, scores });
    expect(items.find((i) => i.label.includes('code SH'))?.status).toBe('needs_review');
  });

  it('marks missing required documents with a recommended action', () => {
    const types: DocumentType[] = ['commercial_invoice'];
    const scores = scoresFor(types);
    const items = buildChecklist({ dossierType: 'import', documentTypes: types, scores });
    const packing = items.find((i) => i.label === 'Liste de colisage');
    expect(packing?.status).toBe('missing');
    expect(packing?.recommendedAction).toMatch(/Ajouter/);
  });

  it('adds a mandatory expert-review item for high-risk dossiers', () => {
    const types: DocumentType[] = ['commercial_invoice'];
    const scores = scoresFor(types, 'facture-vague-sans-fournisseur.pdf');
    expect(scores.expertReviewRequired).toBe(true);
    const items = buildChecklist({ dossierType: 'import', documentTypes: types, scores });
    const review = items.find((i) => i.label === 'Revue experte obligatoire');
    expect(review?.status).toBe('needs_review');
  });
});

describe('buildSupplierQuestions', () => {
  it('derives targeted questions from findings', () => {
    const scores = scoresFor(['commercial_invoice'], 'facture-tva-erreur-vague.pdf');
    const questions = buildSupplierQuestions(scores);
    expect(questions.join(' ')).toMatch(/liste de colisage/i);
    expect(questions.join(' ')).toMatch(/taux de TVA/i);
    expect(questions.join(' ')).toMatch(/désignation précise/i);
  });

  it('returns no questions for a clean dossier', () => {
    const scores = scoresFor(FULL);
    expect(buildSupplierQuestions(scores)).toHaveLength(0);
  });
});
