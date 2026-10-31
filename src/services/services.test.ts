import { describe, expect, it } from 'vitest';
import { authService } from './authService';
import { dossierService } from './dossierService';
import { documentService } from './documentService';
import { alertService } from './alertService';
import { expertReviewService } from './expertReviewService';
import { auditLogService } from './auditLogService';
import { organizationService } from './organizationService';
import { getDb } from './db';

const ctx = { user: { id: 'usr_analyst', name: 'Karim Bennis', organizationId: 'org_demo' } };

describe('authService', () => {
  it('logs in the demo account and records an audit entry', async () => {
    const session = await authService.login('demo@fiscai.ma', 'Demo1234!');
    expect(session.user.email).toBe('demo@fiscai.ma');
    expect(session.token).toBeTruthy();
    expect(getDb().auditLogs.some((l) => l.action === 'auth.login')).toBe(true);
  });

  it('rejects invalid credentials with a helpful message', async () => {
    await expect(authService.login('demo@fiscai.ma', 'WrongPass1!')).rejects.toThrow(/invalides/i);
  });

  it('rejects malformed input before hitting the backend', async () => {
    await expect(authService.login('not-an-email', 'x')).rejects.toThrow();
  });

  it('registers a new user and refuses duplicate emails', async () => {
    const s = await authService.register('Test User', 'new@fiscai.ma', 'Password1!');
    expect(s.user.role).toBe('analyst');
    await expect(authService.register('Again', 'new@fiscai.ma', 'Password1!')).rejects.toThrow(
      /existe déjà/i,
    );
  });
});

describe('dossierService', () => {
  it('lists dossiers with pagination, search, filter, and sort', async () => {
    const all = await dossierService.list('org_demo', { pageSize: 3, page: 1 });
    expect(all.items).toHaveLength(3);
    expect(all.total).toBeGreaterThanOrEqual(5);

    const search = await dossierService.list('org_demo', { search: 'agrumes' });
    expect(search.items.every((d) => d.title.toLowerCase().includes('agrumes'))).toBe(true);

    const imports = await dossierService.list('org_demo', { type: 'import' });
    expect(imports.items.every((d) => d.type === 'import')).toBe(true);

    const asc = await dossierService.list('org_demo', { sortBy: 'createdAt', sortDir: 'asc' });
    const dates = asc.items.map((d) => d.createdAt);
    expect([...dates].sort()).toEqual(dates);
  });

  it('rejects invalid dossier creation and accepts valid input', async () => {
    await expect(
      dossierService.create(ctx, { title: '', clientName: 'X', type: 'import' }),
    ).rejects.toThrow(/obligatoire/);
    const dossier = await dossierService.create(ctx, {
      title: 'Nouveau dossier valide',
      clientName: 'Client',
      type: 'export',
    });
    expect(dossier.status).toBe('draft');
  });

  it('throws a typed NOT_FOUND error for invalid dossier ids', async () => {
    await expect(dossierService.get('org_demo', 'dos_inexistant')).rejects.toThrow(/introuvable/i);
  });

  it('isolates organizations: another org cannot read org_demo dossiers', async () => {
    await expect(dossierService.get('org_autre', 'dos_001')).rejects.toThrow(/introuvable/i);
    const list = await dossierService.list('org_autre');
    expect(list.total).toBe(0);
  });
});

describe('documentService', () => {
  it('uploads a valid file and journals the action', async () => {
    const doc = await documentService.upload(ctx, {
      dossierId: 'dos_001',
      name: 'test.pdf',
      size: 1234,
      mimeType: 'application/pdf',
      documentType: 'packing_list',
    });
    expect(doc.status).toBe('uploaded');
    expect(
      getDb().auditLogs.some((l) => l.action === 'document.uploaded' && l.entityId === doc.id),
    ).toBe(true);
  });

  it('rejects invalid files (type and size)', async () => {
    await expect(
      documentService.upload(ctx, {
        dossierId: 'dos_001',
        name: 'virus.exe',
        size: 100,
        mimeType: 'application/octet-stream',
        documentType: 'other',
      }),
    ).rejects.toThrow(/non supporté/);
    await expect(
      documentService.upload(ctx, {
        dossierId: 'dos_001',
        name: 'gros.pdf',
        size: 20 * 1024 * 1024,
        mimeType: 'application/pdf',
        documentType: 'other',
      }),
    ).rejects.toThrow(/volumineux/);
  });

  it('deletes a document with an audit entry', async () => {
    const doc = await documentService.upload(ctx, {
      dossierId: 'dos_001',
      name: 'a-supprimer.pdf',
      size: 100,
      mimeType: 'application/pdf',
      documentType: 'other',
    });
    await documentService.remove(ctx, doc.id);
    const docs = await documentService.listByDossier('org_demo', 'dos_001');
    expect(docs.some((d) => d.id === doc.id)).toBe(false);
    expect(getDb().auditLogs.some((l) => l.action === 'document.deleted')).toBe(true);
  });
});

describe('alertService', () => {
  it('filters by severity and paginates', async () => {
    const critical = await alertService.list('org_demo', { severity: 'critical' });
    expect(critical.items.every((a) => a.severity === 'critical')).toBe(true);
    const page = await alertService.list('org_demo', { pageSize: 2, page: 1 });
    expect(page.items.length).toBeLessThanOrEqual(2);
  });

  it('updates alert status and reflects active issues on the dossier', async () => {
    const updated = await alertService.updateStatus(ctx, 'alr_001', 'in_review');
    expect(updated.status).toBe('in_review');
    const db = getDb();
    expect(db.dossiers.find((d) => d.id === 'dos_001')?.status).toBe('issue');
    expect(db.auditLogs.some((l) => l.action === 'alert.status_changed')).toBe(true);
  });
});

describe('expertReviewService', () => {
  it('validates the comment and decision', async () => {
    await expect(
      expertReviewService.submit(ctx, {
        dossierId: 'dos_001',
        decision: 'validated',
        comment: 'court',
      }),
    ).rejects.toThrow(/obligatoire/);
  });

  it('submits a review, updates dossier status, and creates an audit entry', async () => {
    const review = await expertReviewService.submit(ctx, {
      dossierId: 'dos_001',
      decision: 'correction_required',
      comment: 'Le code SH doit être confirmé par le transitaire.',
    });
    expect(review.decision).toBe('correction_required');
    const db = getDb();
    expect(db.dossiers.find((d) => d.id === 'dos_001')?.status).toBe('issue');
    expect(db.auditLogs.some((l) => l.action === 'expert_review.submitted')).toBe(true);
  });
});

describe('auditLogService', () => {
  it('records entries with all required fields', () => {
    const entry = auditLogService.record(
      ctx,
      'test.action',
      'dossier',
      'dos_001',
      'Test détail',
      'high',
    );
    expect(entry).toMatchObject({
      userId: 'usr_analyst',
      userName: 'Karim Bennis',
      organizationId: 'org_demo',
      action: 'test.action',
      entityType: 'dossier',
      entityId: 'dos_001',
      riskLevel: 'high',
    });
    expect(entry.id).toBeTruthy();
    expect(entry.timestamp).toBeTruthy();
  });

  it('lists newest entries first and filters by entity', async () => {
    auditLogService.record(ctx, 'a.one', 'dossier', 'dos_002', 'Un');
    auditLogService.record(ctx, 'a.two', 'dossier', 'dos_002', 'Deux');
    const entries = await auditLogService.list('org_demo', { entityId: 'dos_002' });
    expect(entries.length).toBeGreaterThanOrEqual(2);
    expect(entries[0].timestamp >= entries[entries.length - 1].timestamp).toBe(true);
  });
});

describe('organizationService', () => {
  it('updates organization settings with audit', async () => {
    const org = await organizationService.update(ctx, { name: 'Atlas Import SARL', city: 'Rabat' });
    expect(org.name).toBe('Atlas Import SARL');
    expect(getDb().auditLogs.some((l) => l.action === 'settings.changed')).toBe(true);
  });

  it('never exposes passwords through members()', async () => {
    const members = await organizationService.members('org_demo');
    expect(members.length).toBeGreaterThan(0);
    for (const m of members) {
      expect('password' in m).toBe(false);
    }
  });
});
