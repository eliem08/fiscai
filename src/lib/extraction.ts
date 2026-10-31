// Mock document extraction logic. Deterministic so it is fully testable;
// replace with a real OCR/IDP service later (see README, "Mock services").

import type { DocumentFile, DocumentType, ExtractionResult, ExtractedField } from '@/types/models';
import { scanForPromptInjection } from './sanitize';

const REQUIRED_FIELDS: Record<DocumentType, { key: string; label: string }[]> = {
  commercial_invoice: [
    { key: 'supplierName', label: 'Fournisseur' },
    { key: 'supplierTaxId', label: 'Identifiant fiscal fournisseur' },
    { key: 'invoiceNumber', label: 'Numéro de facture' },
    { key: 'totalHT', label: 'Total HT' },
    { key: 'vatRate', label: 'Taux de TVA' },
    { key: 'totalTTC', label: 'Total TTC' },
    { key: 'currency', label: 'Devise' },
    { key: 'productDescription', label: 'Désignation des marchandises' },
  ],
  packing_list: [
    { key: 'packagesCount', label: 'Nombre de colis' },
    { key: 'grossWeight', label: 'Poids brut' },
    { key: 'netWeight', label: 'Poids net' },
  ],
  transport_document: [
    { key: 'carrier', label: 'Transporteur' },
    { key: 'blNumber', label: 'Numéro B/L ou LTA' },
    { key: 'incoterm', label: 'Incoterm' },
  ],
  certificate_origin: [
    { key: 'originCountry', label: "Pays d'origine" },
    { key: 'certificateNumber', label: 'Numéro de certificat' },
  ],
  customs_declaration: [
    { key: 'hsCode', label: 'Code SH' },
    { key: 'declaredValue', label: 'Valeur déclarée' },
    { key: 'regime', label: 'Régime douanier' },
  ],
  vat_declaration: [
    { key: 'period', label: 'Période' },
    { key: 'declaredVat', label: 'TVA déclarée' },
  ],
  other: [],
};

/**
 * Simulated field extraction. Behavior is driven by the file name so demos and
 * tests can force scenarios:
 *  - name contains "incomplet"  -> missing fields
 *  - name contains "flou"       -> low confidence
 *  - name contains "tva-erreur" -> VAT mismatch values
 *  - name contains "vague"      -> vague product description
 *  - name contains "sans-sh"    -> missing HS code
 */
export function extractDocument(doc: Pick<DocumentFile, 'id' | 'name' | 'type'>): ExtractionResult {
  const name = doc.name.toLowerCase();
  const spec = REQUIRED_FIELDS[doc.type] ?? [];
  const lowConfidence = name.includes('flou') || name.includes('scan');
  const incomplete = name.includes('incomplet');
  const baseConfidence = lowConfidence ? 0.48 : 0.93;

  const fields: ExtractedField[] = [];
  const missingFields: string[] = [];
  const warnings: string[] = [];

  for (const f of spec) {
    if (
      incomplete &&
      ['supplierTaxId', 'netWeight', 'incoterm', 'certificateNumber'].includes(f.key)
    ) {
      missingFields.push(f.label);
      continue;
    }
    fields.push({
      key: f.key,
      label: f.label,
      value: mockValue(f.key, name),
      confidence: Math.max(0.2, baseConfidence - (lowConfidence ? 0.1 : 0)),
    });
  }

  if (doc.type === 'other') {
    warnings.push('Type de document non reconnu : extraction limitée.');
  }
  if (lowConfidence) {
    warnings.push('Confiance faible : document peu lisible, vérification humaine recommandée.');
  }

  const injection = scanForPromptInjection(doc.name);
  if (injection.suspicious) {
    warnings.push(
      'Contenu suspect détecté (tentative d’injection d’instructions). Le contenu est traité comme données, jamais comme instructions.',
    );
  }

  return {
    documentId: doc.id,
    documentType: doc.type,
    fields,
    missingFields,
    confidence: doc.type === 'other' ? 0.3 : baseConfidence,
    warnings,
  };
}

function mockValue(key: string, name: string): string | number {
  switch (key) {
    case 'supplierName':
      return name.includes('sans-fournisseur') ? '' : 'Shenzhen Electro Trading Co.';
    case 'supplierTaxId':
      return name.includes('sans-fournisseur') ? '' : 'CN-91440300MA5F';
    case 'invoiceNumber':
      return 'INV-2026-0147';
    case 'totalHT':
      return 184500;
    case 'vatRate':
      return name.includes('tva-erreur') ? 14 : 20;
    case 'totalTTC':
      return name.includes('tva-erreur') ? 218000 : 221400;
    case 'currency':
      return 'MAD';
    case 'productDescription':
      return name.includes('vague')
        ? 'Marchandises diverses'
        : 'Composants électroniques — cartes contrôleurs 12V';
    case 'packagesCount':
      return 42;
    case 'grossWeight':
      return '1 240 kg';
    case 'netWeight':
      return '1 150 kg';
    case 'carrier':
      return 'CMA CGM';
    case 'blNumber':
      return 'BL-CAS-88431';
    case 'incoterm':
      return 'CIF Casablanca';
    case 'originCountry':
      return 'Chine';
    case 'certificateNumber':
      return 'CO-2026-3321';
    case 'hsCode':
      return name.includes('sans-sh') ? '' : '8537.10';
    case 'declaredValue':
      return 184500;
    case 'regime':
      return 'Mise à la consommation';
    case 'period':
      return 'T2 2026';
    case 'declaredVat':
      return 36900;
    default:
      return '';
  }
}
