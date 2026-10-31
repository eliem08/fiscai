// Compliance checklist builder — derives actionable checks from documents and findings.

import type { ChecklistItem, DocumentType, Finding, RiskScores } from '@/types/models';
import { generateId } from './id';

interface ChecklistInput {
  dossierType: 'import' | 'export' | 'fiscal';
  documentTypes: DocumentType[];
  scores: RiskScores;
}

const REQUIRED_DOCS: Record<
  'import' | 'export' | 'fiscal',
  { type: DocumentType; label: string }[]
> = {
  import: [
    { type: 'commercial_invoice', label: 'Facture commerciale' },
    { type: 'packing_list', label: 'Liste de colisage' },
    { type: 'transport_document', label: 'Document de transport (B/L, LTA)' },
    { type: 'certificate_origin', label: 'Certificat d’origine' },
  ],
  export: [
    { type: 'commercial_invoice', label: 'Facture commerciale' },
    { type: 'packing_list', label: 'Liste de colisage' },
    { type: 'transport_document', label: 'Document de transport' },
  ],
  fiscal: [
    { type: 'commercial_invoice', label: 'Factures justificatives' },
    { type: 'vat_declaration', label: 'Déclaration de TVA' },
  ],
};

function hasFinding(scores: RiskScores, code: string): Finding | undefined {
  return scores.findings.find((f) => f.code === code);
}

export function buildChecklist(input: ChecklistInput): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const required = REQUIRED_DOCS[input.dossierType];

  for (const doc of required) {
    const present = input.documentTypes.includes(doc.type);
    items.push({
      id: generateId('chk'),
      label: doc.label,
      status: present ? 'passed' : 'missing',
      detail: present
        ? `${doc.label} fourni(e).`
        : `${doc.label} manquant(e) pour un dossier ${input.dossierType}.`,
      recommendedAction: present ? undefined : `Ajouter : ${doc.label.toLowerCase()}.`,
    });
  }

  const vat = hasFinding(input.scores, 'VAT_MISMATCH');
  items.push({
    id: generateId('chk'),
    label: 'Cohérence TVA (HT / taux / TTC)',
    status: vat ? 'failed' : 'passed',
    detail: vat ? vat.detail : 'Les montants HT, taux de TVA et TTC sont cohérents.',
    recommendedAction: vat?.recommendedAction,
  });

  const hs = hasFinding(input.scores, 'HS_CODE_UNCERTAIN');
  const vague = hasFinding(input.scores, 'VAGUE_DESCRIPTION');
  if (input.dossierType !== 'fiscal') {
    items.push({
      id: generateId('chk'),
      label: 'Classement tarifaire (code SH)',
      status: hs ? 'needs_review' : 'passed',
      detail: hs ? hs.detail : 'Code SH présent et plausible.',
      recommendedAction: hs?.recommendedAction,
    });
    items.push({
      id: generateId('chk'),
      label: 'Désignation des marchandises',
      status: vague ? 'failed' : 'passed',
      detail: vague ? vague.detail : 'Désignation suffisamment précise.',
      recommendedAction: vague?.recommendedAction,
    });
  }

  const supplier = hasFinding(input.scores, 'MISSING_SUPPLIER_IDENTITY');
  items.push({
    id: generateId('chk'),
    label: 'Identité fiscale du fournisseur',
    status: supplier ? 'failed' : 'passed',
    detail: supplier ? supplier.detail : 'Identité et identifiant fiscal du fournisseur présents.',
    recommendedAction: supplier?.recommendedAction,
  });

  if (input.scores.expertReviewRequired) {
    items.push({
      id: generateId('chk'),
      label: 'Revue experte obligatoire',
      status: 'needs_review',
      detail: 'Le niveau de risque exige une validation humaine avant tout usage officiel.',
      recommendedAction: 'Soumettre le dossier à la revue experte.',
    });
  }

  return items;
}

/** Questions to send to the supplier / transitaire, derived from findings. */
export function buildSupplierQuestions(scores: RiskScores): string[] {
  const questions: string[] = [];
  for (const f of scores.findings) {
    switch (f.code) {
      case 'MISSING_PACKING_LIST':
        questions.push(
          'Pouvez-vous transmettre la liste de colisage détaillée (colis, poids brut/net) ?',
        );
        break;
      case 'VAT_MISMATCH':
        questions.push(
          'Pouvez-vous confirmer le taux de TVA appliqué et corriger le total TTC de la facture ?',
        );
        break;
      case 'HS_CODE_UNCERTAIN':
        questions.push(
          'Quel est le code SH exact retenu pour ces marchandises (à confirmer par le transitaire) ?',
        );
        break;
      case 'VAGUE_DESCRIPTION':
        questions.push(
          'Pouvez-vous fournir une désignation précise des marchandises (nature, matière, usage) ?',
        );
        break;
      case 'MISSING_SUPPLIER_IDENTITY':
        questions.push(
          'Pouvez-vous fournir l’identifiant fiscal complet du fournisseur sur la facture ?',
        );
        break;
      case 'MISSING_CERTIFICATE_ORIGIN':
        questions.push(
          'Un certificat d’origine est-il disponible pour bénéficier d’un régime préférentiel ?',
        );
        break;
    }
  }
  return questions;
}
