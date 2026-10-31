import type { Report } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { buildReport } from '@/lib/report';

export const reportService = {
  async generate(ctx: AuditContext, dossierId: string): Promise<Report> {
    await delay(1.5);
    const db = getDb();
    const dossier = db.dossiers.find(
      (d) => d.id === dossierId && d.organizationId === ctx.user.organizationId,
    );
    if (!dossier) throw new ServiceError('NOT_FOUND', 'Dossier introuvable.');
    const organization = db.organizations.find((o) => o.id === ctx.user.organizationId);
    if (!organization) throw new ServiceError('NOT_FOUND', 'Organisation introuvable.');
    const analysis = db.analyses.find(
      (a) => a.dossierId === dossierId && a.organizationId === ctx.user.organizationId,
    );
    if (!analysis) {
      throw new ServiceError(
        'NO_ANALYSIS',
        'Aucune analyse disponible pour ce dossier.',
        'Lancez d’abord l’analyse IA du dossier.',
      );
    }
    const review = db.expertReviews.find((r) => r.dossierId === dossierId);
    const expertReviewStatus: Report['expertReviewStatus'] = review
      ? review.decision === 'validated'
        ? 'validated'
        : 'correction_required'
      : analysis.scores.expertReviewRequired
        ? 'pending'
        : 'not_required';
    const auditSummary = auditLogService.summaryFor(ctx.user.organizationId, dossierId);
    const report = buildReport(organization, dossier, analysis, expertReviewStatus, auditSummary);
    db.reports.unshift(report);
    persist();
    auditLogService.record(
      ctx,
      'report.generated',
      'report',
      report.id,
      `Rapport généré pour le dossier « ${dossier.title} ».`,
      analysis.scores.level,
    );
    return report;
  },

  async list(organizationId: string): Promise<Report[]> {
    await delay(0.5);
    const db = getDb();
    return db.reports.filter((r) => r.organizationId === organizationId);
  },

  async get(organizationId: string, reportId: string): Promise<Report> {
    await delay(0.5);
    const db = getDb();
    const report = db.reports.find((r) => r.id === reportId && r.organizationId === organizationId);
    if (!report) throw new ServiceError('NOT_FOUND', 'Rapport introuvable.');
    return report;
  },

  /** Simulated export: serializes the report as a downloadable text blob. */
  async exportText(ctx: AuditContext, reportId: string): Promise<string> {
    await delay();
    const report = await this.get(ctx.user.organizationId, reportId);
    auditLogService.record(
      ctx,
      'report.exported',
      'report',
      reportId,
      `Export du rapport « ${report.dossierTitle} ».`,
    );
    return [
      `${report.organizationName} — Rapport de pré-contrôle FiscAI PreClear`,
      `Dossier : ${report.dossierTitle} — Client : ${report.clientName}`,
      `Date : ${report.date}`,
      `Scores : fiscal ${report.scores.fiscal}/100 · douane ${report.scores.customs}/100 · global ${report.scores.overall}/100 (${report.scores.level})`,
      '',
      ...report.sections.map((s) => `== ${s.title} ==\n${s.content}\n`),
    ].join('\n');
  },
};
