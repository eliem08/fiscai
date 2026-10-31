import type { Alert, AlertSeverity, AlertStatus, Paginated } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';

export interface AlertQuery {
  severity?: AlertSeverity | 'all';
  status?: AlertStatus | 'all';
  search?: string;
  page?: number;
  pageSize?: number;
}

const SEVERITY_ORDER: Record<AlertSeverity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export const alertService = {
  async list(organizationId: string, query: AlertQuery = {}): Promise<Paginated<Alert>> {
    await delay(0.5);
    const db = getDb();
    let items = db.alerts.filter((a) => a.organizationId === organizationId);
    if (query.severity && query.severity !== 'all')
      items = items.filter((a) => a.severity === query.severity);
    if (query.status && query.status !== 'all')
      items = items.filter((a) => a.status === query.status);
    const search = query.search?.trim().toLowerCase();
    if (search) items = items.filter((a) => a.title.toLowerCase().includes(search));
    items = [...items].sort(
      (a, b) =>
        SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] ||
        b.createdAt.localeCompare(a.createdAt),
    );
    const page = query.page ?? 1;
    const pageSize = query.pageSize ?? 10;
    return {
      items: items.slice((page - 1) * pageSize, page * pageSize),
      total: items.length,
      page,
      pageSize,
    };
  },

  async countOpen(organizationId: string): Promise<number> {
    await delay(0.25);
    const db = getDb();
    return db.alerts.filter((a) => a.organizationId === organizationId && a.status !== 'resolved')
      .length;
  },

  async updateStatus(ctx: AuditContext, alertId: string, status: AlertStatus): Promise<Alert> {
    await delay(0.5);
    const db = getDb();
    const alert = db.alerts.find(
      (a) => a.id === alertId && a.organizationId === ctx.user.organizationId,
    );
    if (!alert) throw new ServiceError('NOT_FOUND', 'Alerte introuvable.');
    alert.status = status;
    alert.updatedAt = new Date().toISOString();

    // Dossier status reflects active critical issues.
    const dossier = db.dossiers.find((d) => d.id === alert.dossierId);
    if (dossier) {
      const activeCritical = db.alerts.some(
        (a) =>
          a.dossierId === alert.dossierId && a.status !== 'resolved' && a.severity === 'critical',
      );
      if (activeCritical && status === 'in_review') dossier.status = 'issue';
      dossier.updatedAt = alert.updatedAt;
    }
    persist();
    auditLogService.record(
      ctx,
      'alert.status_changed',
      'alert',
      alertId,
      `Alerte « ${alert.title} » passée en statut « ${status} ».`,
    );
    return alert;
  },
};
