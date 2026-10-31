import { useEffect, useState } from 'react';
import { ScrollText } from 'lucide-react';
import type { AuditLogEntry } from '@/types/models';
import { auditLogService } from '@/services/auditLogService';
import { useCurrentUser } from '@/store/authStore';
import { formatDateTime } from '@/lib/format';
import { RiskBadge } from '@/components/domain/RiskBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { Pagination } from '@/components/ui/Pagination';

const PAGE_SIZE = 12;

export function AuditLogPage() {
  const user = useCurrentUser();
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    auditLogService
      .list(user.organizationId)
      .then((e) => !cancelled && setEntries(e))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  const paged = entries?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Journal d’audit</h1>
        <p className="text-sm text-slate-500">
          Trace horodatée de toutes les actions importantes : connexions, dossiers, analyses,
          alertes, revues et exports.
        </p>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : entries === null ? (
        <div className="space-y-3" aria-busy="true">
          <SkeletonCard />
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          title="Journal vide"
          description="Les actions apparaîtront ici au fur et à mesure."
          icon={<ScrollText className="h-7 w-7" />}
        />
      ) : (
        <>
          <div className="card overflow-x-auto" data-testid="audit-table">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Journal d’audit de l’organisation</caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Date
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Utilisateur
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Action
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Détails
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Risque
                  </th>
                </tr>
              </thead>
              <tbody>
                {paged.map((e) => (
                  <tr key={e.id} className="border-b border-slate-100 align-top last:border-0">
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {formatDateTime(e.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{e.userName}</td>
                    <td className="px-4 py-3">
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
                        {e.action}
                      </code>
                    </td>
                    <td className="max-w-md px-4 py-3 text-slate-600">{e.details}</td>
                    <td className="px-4 py-3">
                      {e.riskLevel ? (
                        <RiskBadge level={e.riskLevel} />
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={entries.length}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
