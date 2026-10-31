import type { Organization, User } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { sanitizeText } from '@/lib/sanitize';

export const organizationService = {
  async get(organizationId: string): Promise<Organization> {
    await delay(0.5);
    const db = getDb();
    const org = db.organizations.find((o) => o.id === organizationId);
    if (!org) throw new ServiceError('NOT_FOUND', 'Organisation introuvable.');
    return org;
  },

  async members(organizationId: string): Promise<User[]> {
    await delay(0.5);
    const db = getDb();
    return db.users
      .filter((u) => u.organizationId === organizationId)
      .map(({ password: _pw, ...u }) => u);
  },

  async update(
    ctx: AuditContext,
    patch: Partial<Pick<Organization, 'name' | 'city'>>,
  ): Promise<Organization> {
    await delay();
    const db = getDb();
    const org = db.organizations.find((o) => o.id === ctx.user.organizationId);
    if (!org) throw new ServiceError('NOT_FOUND', 'Organisation introuvable.');
    if (patch.name !== undefined) {
      const name = sanitizeText(patch.name, 120);
      if (!name) throw new ServiceError('VALIDATION', 'Le nom de l’organisation est obligatoire.');
      org.name = name;
    }
    if (patch.city !== undefined) org.city = sanitizeText(patch.city, 80);
    persist();
    auditLogService.record(
      ctx,
      'settings.changed',
      'organization',
      org.id,
      'Paramètres de l’organisation mis à jour.',
    );
    return org;
  },
};
