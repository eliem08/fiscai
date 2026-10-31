import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, FileText, FolderKanban, Plus, ShieldAlert } from 'lucide-react';
import type { Dossier } from '@/types/models';
import { dossierService } from '@/services/dossierService';
import { alertService } from '@/services/alertService';
import { reportService } from '@/services/reportService';
import { useCurrentUser } from '@/store/authStore';
import { KpiCard } from '@/components/domain/KpiCard';
import { DossierCard } from '@/components/domain/DossierCard';
import { Disclaimer } from '@/components/domain/Disclaimer';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';

interface DashboardData {
  dossiers: Dossier[];
  totalDossiers: number;
  needsReview: number;
  openAlerts: number;
  reports: number;
}

export function DashboardPage() {
  const user = useCurrentUser();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [dossiers, review, alerts, reports] = await Promise.all([
          dossierService.list(user.organizationId, { pageSize: 4 }),
          dossierService.list(user.organizationId, { status: 'needs_review', pageSize: 1 }),
          alertService.countOpen(user.organizationId),
          reportService.list(user.organizationId),
        ]);
        if (!cancelled) {
          setData({
            dossiers: dossiers.items,
            totalDossiers: dossiers.total,
            needsReview: review.total,
            openAlerts: alerts,
            reports: reports.length,
          });
        }
      } catch (e) {
        if (!cancelled) setError(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tableau de bord</h1>
          <p className="text-sm text-slate-500">
            Vue d’ensemble de vos pré-contrôles fiscaux et douaniers.
          </p>
        </div>
        <Link to="/app/dossiers/new" className="btn-primary" data-testid="new-dossier-cta">
          <Plus className="h-4 w-4" aria-hidden="true" /> Nouveau dossier
        </Link>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : loading || !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="kpi-grid">
            <KpiCard
              label="Dossiers actifs"
              value={data.totalDossiers}
              icon={<FolderKanban className="h-5 w-5" />}
              hint="Tous types confondus"
            />
            <KpiCard
              label="En attente de revue experte"
              value={data.needsReview}
              icon={<ShieldAlert className="h-5 w-5" />}
              tone={data.needsReview > 0 ? 'warning' : 'default'}
              hint="Validation humaine requise"
            />
            <KpiCard
              label="Alertes ouvertes"
              value={data.openAlerts}
              icon={<Bell className="h-5 w-5" />}
              tone={data.openAlerts > 0 ? 'danger' : 'success'}
              hint="Critique → faible"
            />
            <KpiCard
              label="Rapports générés"
              value={data.reports}
              icon={<FileText className="h-5 w-5" />}
              hint="Prêts à transmettre"
            />
          </div>

          <section aria-label="Dossiers récents">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">Dossiers récents</h2>
              <Link to="/app/dossiers" className="text-sm font-medium text-brand-700 underline">
                Voir tous les dossiers
              </Link>
            </div>
            {data.dossiers.length === 0 ? (
              <EmptyState
                title="Aucun dossier pour le moment"
                description="Créez votre premier dossier pour lancer un pré-contrôle fiscal ou douanier."
                action={
                  <Link to="/app/dossiers/new" className="btn-primary">
                    Créer un dossier
                  </Link>
                }
              />
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {data.dossiers.map((d) => (
                  <DossierCard key={d.id} dossier={d} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
      <Disclaimer />
    </div>
  );
}
