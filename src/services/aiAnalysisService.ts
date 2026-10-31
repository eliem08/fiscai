// Agentic analysis pipeline (mocked). Orchestrates the specialized agents,
// produces the AnalysisResult, generates alerts, and updates the dossier.
// Replace agent internals with real LLM/OCR calls later; the orchestration,
// state machine, and safety layers stay.

import type { AgentRun, AnalysisResult, ExtractionResult } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { generateId } from '@/lib/id';
import { extractDocument } from '@/lib/extraction';
import { computeRiskScores } from '@/lib/riskScoring';
import { buildChecklist, buildSupplierQuestions } from '@/lib/checklist';
import { generateAlertsFromFindings } from '@/lib/alertRules';
import { guardSqlQuery } from '@/lib/sqlGuard';

export interface AgentStep {
  agentId: string;
  agentName: string;
  description: string;
}

export const AGENT_PIPELINE: AgentStep[] = [
  {
    agentId: 'intake',
    agentName: 'Agent Intake Documents',
    description: 'Extraction des champs des documents fournis.',
  },
  { agentId: 'tax', agentName: 'Agent Fiscal', description: 'Contrôles TVA et cohérence fiscale.' },
  {
    agentId: 'customs',
    agentName: 'Agent Douane',
    description: 'Contrôles douaniers : documents, code SH, désignation.',
  },
  {
    agentId: 'regulation',
    agentName: 'Agent Réglementation',
    description: 'Références réglementaires applicables (CGI, tarif douanier).',
  },
  {
    agentId: 'compliance',
    agentName: 'Agent Conformité',
    description: 'Construction de la checklist de conformité.',
  },
  {
    agentId: 'fraud',
    agentName: 'Agent Anomalies',
    description: 'Détection d’anomalies et signaux de fraude.',
  },
  {
    agentId: 'report',
    agentName: 'Agent Rapport',
    description: 'Structuration du rapport de pré-contrôle.',
  },
];

export type AnalysisProgress = (step: AgentStep, index: number, total: number) => void;

export const aiAnalysisService = {
  async run(
    ctx: AuditContext,
    dossierId: string,
    onProgress?: AnalysisProgress,
  ): Promise<AnalysisResult> {
    const db = getDb();
    const dossier = db.dossiers.find(
      (d) => d.id === dossierId && d.organizationId === ctx.user.organizationId,
    );
    if (!dossier) throw new ServiceError('NOT_FOUND', 'Dossier introuvable.');
    if (dossier.title.toLowerCase().includes('[fail-analysis]')) {
      // Test/demo hook to exercise the failure path end to end.
      throw new ServiceError(
        'ANALYSIS_FAILED',
        'L’analyse IA a échoué (erreur simulée du moteur).',
        'Réessayez dans quelques instants ou contactez le support.',
      );
    }

    dossier.status = 'analyzing';
    persist();
    auditLogService.record(
      ctx,
      'analysis.launched',
      'dossier',
      dossierId,
      `Lancement de l’analyse IA du dossier « ${dossier.title} ».`,
    );

    const documents = db.documents.filter(
      (d) => d.dossierId === dossierId && d.organizationId === ctx.user.organizationId,
    );

    // --- Pipeline execution ---
    const extractions: ExtractionResult[] = [];
    const agentRuns: AgentRun[] = [];

    for (let i = 0; i < AGENT_PIPELINE.length; i++) {
      const step = AGENT_PIPELINE[i];
      onProgress?.(step, i, AGENT_PIPELINE.length);
      await delay(0.8);
      if (step.agentId === 'intake') {
        for (const doc of documents) {
          extractions.push(extractDocument(doc));
          doc.status = 'extracted';
        }
      }
    }

    const documentTypes = documents.map((d) => d.type);
    const scores = computeRiskScores({
      dossierType: dossier.type,
      documentTypes,
      extractions,
    });
    const checklist = buildChecklist({ dossierType: dossier.type, documentTypes, scores });
    const supplierQuestions = buildSupplierQuestions(scores);
    const lowConfidence = scores.confidence < 0.6;
    const partial = documents.length === 0 || extractions.length === 0;

    // Per-agent results, statuses, and evidence.
    const findingsByDomain = (domain: string) => scores.findings.filter((f) => f.domain === domain);
    for (const step of AGENT_PIPELINE) {
      let findings: string[] = [];
      let evidence: string[] = [];
      let status: AgentRun['status'] = 'completed';
      let confidence = scores.confidence;
      let recommendedAction = 'Aucune action requise.';

      switch (step.agentId) {
        case 'intake':
          findings = extractions.map(
            (e) =>
              `${e.documentType} : ${e.fields.length} champs extraits, confiance ${(e.confidence * 100).toFixed(0)}%.`,
          );
          evidence = extractions.flatMap((e) => e.warnings);
          if (extractions.length === 0) {
            status = 'needs_review';
            findings = ['Aucun document analysable.'];
            recommendedAction = 'Ajouter les documents du dossier.';
          }
          break;
        case 'tax':
          findings = findingsByDomain('fiscal').map((f) => f.title);
          evidence = findingsByDomain('fiscal').map((f) => f.evidence ?? f.detail);
          recommendedAction = findingsByDomain('fiscal')[0]?.recommendedAction ?? recommendedAction;
          break;
        case 'customs':
          findings = findingsByDomain('customs').map((f) => f.title);
          evidence = findingsByDomain('customs').map((f) => f.detail);
          recommendedAction =
            findingsByDomain('customs')[0]?.recommendedAction ?? recommendedAction;
          break;
        case 'regulation':
          findings = ['Références applicables identifiées.'];
          evidence = [
            'Code Général des Impôts (CGI) 2026 — art. 89 à 106 (TVA).',
            'Tarif des douanes — chapitre correspondant au code SH déclaré.',
            'Circulaire ADII n° 6335/210 relative aux documents exigibles.',
          ];
          break;
        case 'compliance':
          findings = checklist.map((c) => `${c.label} : ${c.status}`);
          recommendedAction =
            checklist.find((c) => c.recommendedAction)?.recommendedAction ?? recommendedAction;
          break;
        case 'fraud': {
          const anomalies = scores.findings.filter(
            (f) => f.severity === 'critical' || f.severity === 'high',
          );
          findings = anomalies.map((f) => f.title);
          evidence = anomalies.map((f) => f.detail);
          if (anomalies.length > 0) {
            status = 'needs_review';
            recommendedAction = 'Vérification humaine des anomalies détectées.';
          }
          break;
        }
        case 'report':
          findings = ['Rapport structuré prêt à générer.'];
          break;
      }
      if (lowConfidence && status === 'completed') {
        status = 'needs_review';
        confidence = scores.confidence;
      }
      agentRuns.push({
        agentId: step.agentId,
        agentName: step.agentName,
        description: step.description,
        status,
        confidence,
        findings,
        evidence,
        recommendedAction,
      });
    }

    const analysis: AnalysisResult = {
      id: generateId('ana'),
      dossierId,
      organizationId: ctx.user.organizationId,
      createdAt: new Date().toISOString(),
      scores,
      extractions,
      checklist,
      agentRuns,
      supplierQuestions,
      lowConfidence,
      partial,
    };

    // Persist analysis, replace previous alerts for this dossier, update status.
    db.analyses = db.analyses.filter((a) => a.dossierId !== dossierId);
    db.analyses.push(analysis);
    const newAlerts = generateAlertsFromFindings(scores.findings, {
      organizationId: ctx.user.organizationId,
      dossierId,
    });
    db.alerts = db.alerts.filter((a) => a.dossierId !== dossierId).concat(newAlerts);
    dossier.status = scores.expertReviewRequired ? 'needs_review' : 'analyzed';
    dossier.updatedAt = analysis.createdAt;
    persist();

    auditLogService.record(
      ctx,
      'analysis.completed',
      'dossier',
      dossierId,
      `Analyse terminée : score global ${scores.overall}/100 (${scores.level}), ${newAlerts.length} alerte(s) générée(s).`,
      scores.level,
    );
    return analysis;
  },

  async getLatest(organizationId: string, dossierId: string): Promise<AnalysisResult | null> {
    await delay(0.5);
    const db = getDb();
    return (
      db.analyses.find((a) => a.dossierId === dossierId && a.organizationId === organizationId) ??
      null
    );
  },

  /** Data Query Agent entry point — read-only by design. */
  async queryData(
    _ctx: AuditContext,
    naturalLanguageOrSql: string,
  ): Promise<{ blocked: boolean; message: string }> {
    await delay(0.5);
    const guard = guardSqlQuery(naturalLanguageOrSql);
    if (!guard.allowed) {
      return { blocked: true, message: guard.reason ?? 'Requête bloquée.' };
    }
    return { blocked: false, message: 'Requête autorisée (lecture seule).' };
  },
};
