import { useEffect, useState } from 'react';
import { BellOff } from 'lucide-react';
import type { Alert, AlertSeverity, AlertStatus } from '@/types/models';
import { alertService } from '@/services/alertService';
import { useCurrentUser } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { ALERT_STATUS_LABELS, SEVERITY_LABELS } from '@/lib/constants';
import { AlertCard } from '@/components/domain/AlertCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { Pagination } from '@/components/ui/Pagination';

const PAGE_SIZE = 6;

export function AlertsPage() {
  const user = useCurrentUser();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<AlertSeverity | 'all'>('all');
  const [status, setStatus] = useState<AlertStatus | 'all'>('all');
  const [error, setError] = useState<unknown>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    alertService
      .list(user.organizationId, { severity, status, page, pageSize: PAGE_SIZE })
      .then((res) => {
        if (!cancelled) {
          setAlerts(res.items);
          setTotal(res.total);
        }
      })
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, severity, status, page, reloadKey]);

  async function changeStatus(alert: Alert, next: AlertStatus) {
    if (!user) return;
    setBusyId(alert.id);
    try {
      await alertService.updateStatus({ user }, alert.id, next);
      toast('success', `Alerte « ${alert.title} » mise à jour (${ALERT_STATUS_LABELS[next]}).`);
      setReloadKey((k) => k + 1);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Mise à jour impossible.');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Centre d’alertes</h1>
        <p className="text-sm text-slate-500">
          Alertes générées par l’analyse IA, triées par sévérité. Traitez-les jusqu’à résolution.
        </p>
      </div>

      <div className="card flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="label" htmlFor="alert-severity-filter">
            Sévérité
          </label>
          <select
            id="alert-severity-filter"
            className="input"
            value={severity}
            onChange={(e) => {
              setSeverity(e.target.value as AlertSeverity | 'all');
              setPage(1);
            }}
          >
            <option value="all">Toutes</option>
            {Object.entries(SEVERITY_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="alert-status-filter">
            Statut
          </label>
          <select
            id="alert-status-filter"
            className="input"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as AlertStatus | 'all');
              setPage(1);
            }}
          >
            <option value="all">Tous</option>
            {Object.entries(ALERT_STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : alerts === null ? (
        <div className="space-y-3" aria-busy="true">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : alerts.length === 0 ? (
        <EmptyState
          title="Aucune alerte"
          description="Aucune alerte ne correspond à ces filtres. Bon signe !"
          icon={<BellOff className="h-7 w-7" />}
        />
      ) : (
        <>
          <div className="space-y-3" data-testid="alert-list">
            {alerts.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                busy={busyId === a.id}
                onStatusChange={(next) => void changeStatus(a, next)}
              />
            ))}
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
