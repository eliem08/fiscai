import { describe, expect, it } from 'vitest';
import { aiAnalysisService, AGENT_PIPELINE } from './aiAnalysisService';
import { documentService } from './documentService';
import { dossierService } from './dossierService';
import { getDb } from './db';
import { seedUsers } from '@/mocks/seed';

const user = { id: seedUsers[1].id, name: seedUsers[1].name, organizationId: 'org_demo' };
const ctx = { user };

async function createImportDossier() {
  return dossierService.create(ctx, {
    title: 'Import test agents',
    clientName: 'Client Test',
    type: 'import',
  });
}

describe('aiAnalysisService (agent pipeline)', () => {
  it('runs the full pipeline and reports progress for each agent', async () => {
    const dossier = await createImportDossier();
    const steps: string[] = [];
    const result = await aiAnalysisService.run(ctx, dossier.id, (step) => steps.push(step.agentId));
    expect(steps).toEqual(AGENT_PIPELINE.map((s) => s.agentId));
    expect(result.agentRuns).toHaveLength(AGENT_PIPELINE.length);
  });

  it('Document Intake Agent returns extracted fields', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    expect(result.extractions).toHaveLength(1);
    expect(result.extractions[0].fields.length).toBeGreaterThan(0);
    const intake = result.agentRuns.find((r) => r.agentId === 'intake');
    expect(intake?.findings.join(' ')).toMatch(/champs extraits/);
  });

  it('Tax Agent detects VAT mismatch', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture-tva-erreur.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    const tax = result.agentRuns.find((r) => r.agentId === 'tax');
    expect(tax?.findings.join(' ')).toMatch(/TVA/);
  });

  it('Customs Agent detects a missing packing list', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    const customs = result.agentRuns.find((r) => r.agentId === 'customs');
    expect(customs?.findings.join(' ')).toMatch(/colisage/i);
  });

  it('Regulation Agent returns mock source references', async () => {
    const dossier = await createImportDossier();
    const result = await aiAnalysisService.run(ctx, dossier.id);
    const regulation = result.agentRuns.find((r) => r.agentId === 'regulation');
    expect(regulation?.evidence.join(' ')).toMatch(/Code Général des Impôts/);
    expect(regulation?.evidence.join(' ')).toMatch(/douanes/i);
  });

  it('Compliance Agent creates a checklist', async () => {
    const dossier = await createImportDossier();
    const result = await aiAnalysisService.run(ctx, dossier.id);
    expect(result.checklist.length).toBeGreaterThan(0);
    const compliance = result.agentRuns.find((r) => r.agentId === 'compliance');
    expect(compliance?.findings.length).toBe(result.checklist.length);
  });

  it('Fraud Agent flags anomalies and requires human review', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture-vague-sans-fournisseur.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    const fraud = result.agentRuns.find((r) => r.agentId === 'fraud');
    expect(fraud?.status).toBe('needs_review');
    expect(fraud?.findings.length).toBeGreaterThan(0);
  });

  it('flags low-confidence analysis via the verification layer', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture-flou.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    expect(result.lowConfidence).toBe(true);
  });

  it('requires human review for high-risk cases (dossier status)', async () => {
    const dossier = await createImportDossier();
    await documentService.upload(ctx, {
      dossierId: dossier.id,
      name: 'facture-vague-sans-fournisseur.pdf',
      size: 1000,
      mimeType: 'application/pdf',
      documentType: 'commercial_invoice',
    });
    const result = await aiAnalysisService.run(ctx, dossier.id);
    expect(result.scores.expertReviewRequired).toBe(true);
    const updated = await dossierService.get('org_demo', dossier.id);
    expect(updated.status).toBe('needs_review');
  });

  it('generates alerts and audit log entries from the analysis', async () => {
    const dossier = await createImportDossier();
    await aiAnalysisService.run(ctx, dossier.id);
    const db = getDb();
    expect(db.alerts.some((a) => a.dossierId === dossier.id)).toBe(true);
    expect(
      db.auditLogs.some((l) => l.entityId === dossier.id && l.action === 'analysis.completed'),
    ).toBe(true);
  });

  it('fails cleanly when the engine errors, keeping a typed message', async () => {
    const dossier = await dossierService.create(ctx, {
      title: '[fail-analysis] Import KO',
      clientName: 'Client',
      type: 'import',
    });
    await expect(aiAnalysisService.run(ctx, dossier.id)).rejects.toThrow(/analyse ia a échoué/i);
  });

  it('Data Query Agent blocks unsafe SQL-like operations', async () => {
    const blocked = await aiAnalysisService.queryData(ctx, 'DROP TABLE dossiers');
    expect(blocked.blocked).toBe(true);
    expect(blocked.message).toMatch(/lecture seule/i);
    const ok = await aiAnalysisService.queryData(ctx, 'SELECT * FROM dossiers');
    expect(ok.blocked).toBe(false);
  });
});
