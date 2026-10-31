import type { Dossier, DossierStatus, Paginated } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { generateId } from '@/lib/id';
import { sanitizeText } from '@/lib/sanitize';
import { validateDossierForm, type DossierFormValues } from '@/lib/validation';

export interface DossierQuery {
  search?: string;
  status?: DossierStatus | 'all';
  type?: Dossier['type'] | 'all';
  sortBy?: 'updatedAt' | 'createdAt' | 'title';
  sortDir?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
}

export const dossierService = {
  async list(organizationId: string, query: DossierQuery = {}): Promise<Paginated<Dossier>> {
    await delay();
    const db = getDb();
    let items = db.dossiers.filter((d) => d.organizationId === organizationId);

    const search = query.search?.trim().toLowerCase();
    if (search) {
      items = items.filter(
        (d) =>
          d.title.toLowerCase().includes(search) || d.clientName.toLowerCase().includes(search),
      );
    }
    if (query.status && query.status !== 'all')
      items = items.filter((d) => d.status === query.status);
    if (query.type && query.type !== 'all') items = items.filter((d) => d.type === query.type);

    const sortBy = query.sortBy ?? 'updatedAt';
    const dir = query.sortDir === 'asc' ? 1 : -1;
    items = [...items].sort((a, b) => a[sortBy].localeCompare(b[sortBy]) * dir);

    const page = query.page ?? 1;
    const pageSize = query.pageSize ?? 10;
    return {
      items: items.slice((page - 1) * pageSize, page * pageSize),
      total: items.length,
      page,
      pageSize,
    };
  },

  async get(organizationId: string, id: string): Promise<Dossier> {
    await delay(0.5);
    const db = getDb();
    const dossier = db.dossiers.find((d) => d.id === id && d.organizationId === organizationId);
    if (!dossier) {
      throw new ServiceError(
        'NOT_FOUND',
        'Dossier introuvable.',
        'Vérifiez le lien ou retournez à la liste des dossiers.',
      );
    }
    return dossier;
  },

  async create(ctx: AuditContext, values: DossierFormValues): Promise<Dossier> {
    const check = validateDossierForm(values);
    if (!check.valid) throw new ServiceError('VALIDATION', check.errors[0].message);
    await delay();
    const db = getDb();
    const now = new Date().toISOString();
    const dossier: Dossier = {
      id: generateId('dos'),
      organizationId: ctx.user.organizationId,
      title: sanitizeText(values.title, 140),
      clientName: sanitizeText(values.clientName, 140),
      type: values.type as Dossier['type'],
      status: 'draft',
      description: values.description ? sanitizeText(values.description, 800) : undefined,
      referenceBadr: values.referenceBadr || undefined,
      createdBy: ctx.user.id,
      createdAt: now,
      updatedAt: now,
    };
    db.dossiers.unshift(dossier);
    persist();
    auditLogService.record(
      ctx,
      'dossier.created',
      'dossier',
      dossier.id,
      `Création du dossier « ${dossier.title} ».`,
    );
    return dossier;
  },

  async updateStatus(
    ctx: AuditContext,
    id: string,
    status: DossierStatus,
    reason?: string,
  ): Promise<Dossier> {
    await delay(0.5);
    const db = getDb();
    const dossier = db.dossiers.find(
      (d) => d.id === id && d.organizationId === ctx.user.organizationId,
    );
    if (!dossier) throw new ServiceError('NOT_FOUND', 'Dossier introuvable.');
    dossier.status = status;
    dossier.updatedAt = new Date().toISOString();
    persist();
    auditLogService.record(
      ctx,
      'dossier.status_changed',
      'dossier',
      id,
      `Statut du dossier changé en « ${status} »${reason ? ` — ${reason}` : ''}.`,
    );
    return dossier;
  },
};
