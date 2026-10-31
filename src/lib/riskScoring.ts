// Risk scoring engine — pure, deterministic, unit-tested.
// Scores are 0..100 (higher = riskier). Level thresholds:
//   low < 25 <= medium < 50 <= high < 75 <= critical

import type {
  AlertSeverity,
  DocumentType,
  ExtractionResult,
  Finding,
  RiskLevel,
  RiskScores,
} from '@/types/models';
import { generateId } from './id';

export interface ScoringInput {
  dossierType: 'import' | 'export' | 'fiscal';
  documentTypes: DocumentType[];
  extractions: ExtractionResult[];
}

const LEVEL_THRESHOLDS: [RiskLevel, number][] = [
  ['critical', 75],
  ['high', 50],
  ['medium', 25],
  ['low', 0],
];

export function levelForScore(score: number): RiskLevel {
  for (const [level, min] of LEVEL_THRESHOLDS) {
    if (score >= min) return level;
  }
  return 'low';
}

function finding(
  domain: Finding['domain'],
  code: string,
  severity: AlertSeverity,
  title: string,
  detail: string,
  recommendedAction: string,
  evidence?: string,
): Finding {
  return {
    id: generateId('fnd'),
    domain,
    code,
    severity,
    title,
    detail,
    recommendedAction,
    evidence,
  };
}

function getField(
  extractions: ExtractionResult[],
  key: string,
): string | number | null | undefined {
  for (const ex of extractions) {
    const f = ex.fields.find((fl) => fl.key === key);
    if (f) return f.value;
  }
  return undefined;
}

export function computeRiskScores(input: ScoringInput): RiskScores {
  const { dossierType, documentTypes, extractions } = input;
  const findings: Finding[] = [];
  let fiscal = 5;
  let customs = 5;
  const isCustomsDossier = dossierType !== 'fiscal';

  // --- Missing packing list (customs) ---
  if (isCustomsDossier && !documentTypes.includes('packing_list')) {
    customs += 30;
    findings.push(
      finding(
        'customs',
        'MISSING_PACKING_LIST',
        'critical',
        'Liste de colisage manquante',
        'Aucune liste de colisage (packing list) n’a été fournie. Ce document est exigé pour le dédouanement BADR.',
        'Demander la liste de colisage au fournisseur avant le dépôt du dossier.',
      ),
    );
  }

  // --- Missing certificate of origin (warning) ---
  if (isCustomsDossier && !documentTypes.includes('certificate_origin')) {
    customs += 8;
    findings.push(
      finding(
        'customs',
        'MISSING_CERTIFICATE_ORIGIN',
        'low',
        'Certificat d’origine absent',
        'Le certificat d’origine n’a pas été fourni. Il peut conditionner un traitement tarifaire préférentiel.',
        'Vérifier avec le transitaire si un certificat d’origine est requis pour ce régime.',
      ),
    );
  }

  // --- VAT consistency (fiscal) ---
  const totalHT = Number(getField(extractions, 'totalHT'));
  const vatRate = Number(getField(extractions, 'vatRate'));
  const totalTTC = Number(getField(extractions, 'totalTTC'));
  if (Number.isFinite(totalHT) && Number.isFinite(vatRate) && Number.isFinite(totalTTC)) {
    const expected = Math.round(totalHT * (1 + vatRate / 100));
    if (Math.abs(expected - totalTTC) > Math.max(1, totalHT * 0.001)) {
      fiscal += 28;
      findings.push(
        finding(
          'fiscal',
          'VAT_MISMATCH',
          'medium',
          'Incohérence TVA détectée',
          `Total TTC (${totalTTC}) incohérent avec HT (${totalHT}) au taux de ${vatRate}% (attendu ≈ ${expected}).`,
          'Faire corriger la facture par le fournisseur ou justifier l’écart avant déclaration.',
          `HT=${totalHT}, taux=${vatRate}%, TTC=${totalTTC}`,
        ),
      );
    }
  }

  // --- Supplier identity (fiscal + customs) ---
  const supplierName = getField(extractions, 'supplierName');
  const supplierTaxId = getField(extractions, 'supplierTaxId');
  const supplierMissing =
    extractions.length > 0 && (!supplierName || !supplierTaxId || supplierTaxId === '');
  if (supplierMissing) {
    fiscal += 18;
    customs += 12;
    findings.push(
      finding(
        'fiscal',
        'MISSING_SUPPLIER_IDENTITY',
        'high',
        'Identité fournisseur incomplète',
        'Le nom ou l’identifiant fiscal du fournisseur est absent de la facture commerciale.',
        'Obtenir une facture avec l’identité fiscale complète du fournisseur.',
      ),
    );
  }

  // --- HS code (customs) ---
  const hsCode = getField(extractions, 'hsCode');
  const hasCustomsDecl = documentTypes.includes('customs_declaration');
  if (isCustomsDossier && (hsCode === '' || (hasCustomsDecl && hsCode == null))) {
    customs += 22;
    findings.push(
      finding(
        'customs',
        'HS_CODE_UNCERTAIN',
        'high',
        'Code SH incertain ou manquant',
        'Le code SH (position tarifaire) est absent ou incertain, ce qui expose à un blocage ou un redressement.',
        'Faire confirmer la position tarifaire par le transitaire avant la déclaration BADR.',
      ),
    );
  }

  // --- Vague product description (customs) ---
  const description = String(getField(extractions, 'productDescription') ?? '');
  if (
    isCustomsDossier &&
    description &&
    (description.length < 15 || /divers|général|misc/i.test(description))
  ) {
    customs += 15;
    findings.push(
      finding(
        'customs',
        'VAGUE_DESCRIPTION',
        'high',
        'Désignation des marchandises trop vague',
        `La désignation « ${description} » est insuffisante pour un classement tarifaire fiable.`,
        'Demander une désignation précise (nature, matière, usage) au fournisseur.',
      ),
    );
  }

  // --- Low extraction confidence (general) ---
  const lowConf = extractions.some((e) => e.confidence < 0.6);
  if (lowConf) {
    fiscal += 8;
    customs += 8;
    findings.push(
      finding(
        'general',
        'LOW_EXTRACTION_CONFIDENCE',
        'medium',
        'Extraction à faible confiance',
        'Au moins un document est peu lisible : les valeurs extraites doivent être vérifiées manuellement.',
        'Fournir des documents de meilleure qualité ou vérifier les champs extraits.',
      ),
    );
  }

  // --- No documents at all ---
  if (extractions.length === 0) {
    fiscal += 20;
    customs += 20;
    findings.push(
      finding(
        'general',
        'NO_DOCUMENTS',
        'high',
        'Aucun document analysable',
        'Le dossier ne contient aucun document exploitable : analyse partielle uniquement.',
        'Ajouter au minimum la facture commerciale et le document de transport.',
      ),
    );
  }

  fiscal = Math.min(100, Math.round(fiscal));
  customs = Math.min(100, Math.round(customs));
  const overall = Math.min(
    100,
    // Customs dossiers weight the customs score heavily so a severe customs
    // profile cannot be diluted by a clean fiscal side.
    Math.round(isCustomsDossier ? 0.35 * fiscal + 0.65 * customs : 0.8 * fiscal + 0.2 * customs),
  );
  const level = levelForScore(overall);
  const confidence =
    extractions.length === 0 ? 0.4 : Math.min(...extractions.map((e) => e.confidence));

  return {
    fiscal,
    customs,
    overall,
    level,
    expertReviewRequired: level === 'high' || level === 'critical',
    findings,
    confidence,
  };
}
