import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText } from 'lucide-react';
import type { Report } from '@/types/models';
import { reportService } from '@/services/reportService';
import { useCurrentUser } from '@/store/authStore';
import { formatDateTime } from '@/lib/format';
import { RiskBadge } from '@/components/domain/RiskBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';

export function ReportsPage() {
  const user = useCurrentUser();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    reportService
      .list(user.organizationId)
      .then((r) => !cancelled && setReports(r))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Rapports</h1>
        <p className="text-sm text-slate-500">
          Rapports de pré-contrôle générés, prêts à transmettre à vos experts.
        </p>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : reports === null ? (
        <div className="space-y-3" aria-busy="true">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : reports.length === 0 ? (
        <EmptyState
          title="Aucun rapport généré"
          description="Générez un rapport depuis la page d’analyse d’un dossier."
          icon={<FileText className="h-7 w-7" />}
          action={
            <Link to="/app/dossiers" className="btn-primary">
              Voir les dossiers
            </Link>
          }
        />
      ) : (
        <ul className="space-y-3" data-testid="report-list">
          {reports.map((r) => (
            <li key={r.id}>
              <Link
                to={`/app/reports/${r.id}`}
                className="card flex flex-wrap items-center justify-between gap-3 p-5 transition hover:border-brand-300"
                aria-label={`Ouvrir le rapport ${r.dossierTitle}`}
              >
                <div>
                  <p className="font-semibold text-slate-900">{r.dossierTitle}</p>
                  <p className="text-sm text-slate-500">
                    {r.clientName} · {formatDateTime(r.date)}
                  </p>
                </div>
                <RiskBadge level={r.scores.level} score={r.scores.overall} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
