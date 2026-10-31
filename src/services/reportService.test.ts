import { describe, expect, it } from 'vitest';
import { reportService } from './reportService';
import { aiAnalysisService } from './aiAnalysisService';
import { dossierService } from './dossierService';
import { documentService } from './documentService';
import { expertReviewService } from './expertReviewService';
import { REQUIRED_REPORT_SECTIONS } from '@/lib/report';
import { LEGAL_DISCLAIMER } from '@/lib/constants';

const ctx = { user: { id: 'usr_analyst', name: 'Karim Bennis', organizationId: 'org_demo' } };

async function analyzedDossier() {
  const dossier = await dossierService.create(ctx, {
    title: 'Import rapport test',
    clientName: 'Client Rapport',
    type: 'import',
  });
  await documentService.upload(ctx, {
    dossierId: dossier.id,
    name: 'facture.pdf',
    size: 1000,
    mimeType: 'application/pdf',
    documentType: 'commercial_invoice',
  });
  await aiAnalysisService.run(ctx, dossier.id);
  return dossier;
}

describe('reportService (Report Agent)', () => {
  it('refuses to generate a report without an analysis', async () => {
    const dossier = await dossierService.create(ctx, {
      title: 'Sans analyse',
      clientName: 'Client',
      type: 'import',
    });
    await expect(reportService.generate(ctx, dossier.id)).rejects.toThrow(/aucune analyse/i);
  });

  it('creates a structured report containing every required section', async () => {
    const dossier = await analyzedDossier();
    const report = await reportService.generate(ctx, dossier.id);
    const keys = report.sections.map((s) => s.key);
    for (const required of REQUIRED_REPORT_SECTIONS) {
      expect(keys).toContain(required);
    }
    expect(report.organizationName).toBe('Atlas Import Export SARL');
    expect(report.clientName).toBe('Client Rapport');
    expect(report.dossierTitle).toBe('Import rapport test');
    expect(report.date).toBeTruthy();
    expect(report.scores.overall).toBeGreaterThanOrEqual(0);
    expect(report.disclaimer).toBe(LEGAL_DISCLAIMER);
  });

  it('includes the audit trail summary and expert review status', async () => {
    const dossier = await analyzedDossier();
    const report = await reportService.generate(ctx, dossier.id);
    const audit = report.sections.find((s) => s.key === 'audit_trail');
    expect(audit?.content).toMatch(/Création du dossier|Lancement de l’analyse/);
    expect(['pending', 'validated', 'correction_required', 'not_required']).toContain(
      report.expertReviewStatus,
    );
  });

  it('reflects the expert decision after a review is submitted', async () => {
    const dossier = await analyzedDossier();
    await expertReviewService.submit(
      { user: { id: 'usr_expert', name: 'Salma Idrissi', organizationId: 'org_demo' } },
      {
        dossierId: dossier.id,
        decision: 'correction_required',
        comment: 'Corriger la facture avant dépôt.',
      },
    );
    const report = await reportService.generate(ctx, dossier.id);
    expect(report.expertReviewStatus).toBe('correction_required');
  });

  it('exports the report as text including the disclaimer', async () => {
    const dossier = await analyzedDossier();
    const report = await reportService.generate(ctx, dossier.id);
    const text = await reportService.exportText(ctx, report.id);
    expect(text).toContain('Rapport de pré-contrôle');
    expect(text).toContain(LEGAL_DISCLAIMER);
  });
});
