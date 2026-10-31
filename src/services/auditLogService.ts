import type { AuditLogEntry, RiskLevel, User } from '@/types/models';
import { getDb, persist, delay } from './db';
import { generateId } from '@/lib/id';
import { sanitizeText } from '@/lib/sanitize';

export interface AuditContext {
  user: Pick<User, 'id' | 'name' | 'organizationId'>;
}

export const auditLogService = {
  /** Synchronous on purpose: called from inside other service operations. */
  record(
    ctx: AuditContext,
    action: string,
    entityType: string,
    entityId: string,
    details: string,
    riskLevel?: RiskLevel,
  ): AuditLogEntry {
    const db = getDb();
    const entry: AuditLogEntry = {
      id: generateId('aud'),
      userId: ctx.user.id,
      userName: ctx.user.name,
      organizationId: ctx.user.organizationId,
      action,
      entityType,
      entityId,
      timestamp: new Date().toISOString(),
      details: sanitizeText(details, 500),
      riskLevel,
    };
    db.auditLogs.unshift(entry);
    persist();
    return entry;
  },

  async list(organizationId: string, opts?: { entityId?: string; limit?: number }) {
    await delay(0.5);
    const db = getDb();
    let items = db.auditLogs.filter((a) => a.organizationId === organizationId);
    if (opts?.entityId) items = items.filter((a) => a.entityId === opts.entityId);
    items = [...items].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    return opts?.limit ? items.slice(0, opts.limit) : items;
  },

  summaryFor(organizationId: string, dossierId: string): string {
    const db = getDb();
    const entries = db.auditLogs
      .filter((a) => a.organizationId === organizationId && a.entityId === dossierId)
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    if (entries.length === 0) return 'Aucune action enregistrée pour ce dossier.';
    return entries
      .map((e) => `${e.timestamp.slice(0, 16).replace('T', ' ')} — ${e.details}`)
      .join('\n');
  },
};
