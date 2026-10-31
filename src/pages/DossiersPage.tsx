import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
import type { Dossier, DossierStatus } from '@/types/models';
import { dossierService } from '@/services/dossierService';
import { useCurrentUser } from '@/store/authStore';
import { DOSSIER_STATUS_LABELS, DOSSIER_TYPE_LABELS } from '@/lib/constants';
import { DossierCard } from '@/components/domain/DossierCard';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Pagination } from '@/components/ui/Pagination';

const PAGE_SIZE = 6;

export function DossiersPage() {
  const user = useCurrentUser();
  const [items, setItems] = useState<Dossier[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<DossierStatus | 'all'>('all');
  const [type, setType] = useState<Dossier['type'] | 'all'>('all');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    dossierService
      .list(user.organizationId, { search, status, type, page, pageSize: PAGE_SIZE, sortDir })
      .then((res) => {
        if (!cancelled) {
          setItems(res.items);
          setTotal(res.total);
        }
      })
      .catch((e) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [user, search, status, type, page, sortDir, reloadKey]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dossiers</h1>
          <p className="text-sm text-slate-500">
            Recherchez, filtrez et suivez vos dossiers de pré-contrôle.
          </p>
        </div>
        <Link to="/app/dossiers/new" className="btn-primary">
          <Plus className="h-4 w-4" aria-hidden="true" /> Nouveau dossier
        </Link>
      </div>

      <div className="card flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-52 flex-1">
          <label className="label" htmlFor="dossier-search">
            Recherche
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              id="dossier-search"
              className="input pl-9"
              placeholder="Titre ou client…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="dossier-status-filter">
            Statut
          </label>
          <select
            id="dossier-status-filter"
            className="input"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as DossierStatus | 'all');
              setPage(1);
            }}
          >
            <option value="all">Tous</option>
            {Object.entries(DOSSIER_STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="dossier-type-filter">
            Type
          </label>
          <select
            id="dossier-type-filter"
            className="input"
            value={type}
            onChange={(e) => {
              setType(e.target.value as Dossier['type'] | 'all');
              setPage(1);
            }}
          >
            <option value="all">Tous</option>
            {Object.entries(DOSSIER_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="dossier-sort">
            Tri
          </label>
          <select
            id="dossier-sort"
            className="input"
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value as 'asc' | 'desc')}
          >
            <option value="desc">Plus récents d’abord</option>
            <option value="asc">Plus anciens d’abord</option>
          </select>
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : loading ? (
        <div className="grid gap-4 lg:grid-cols-2" aria-busy="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Aucun dossier trouvé"
          description={
            search || status !== 'all' || type !== 'all'
              ? 'Aucun dossier ne correspond à vos filtres.'
              : 'Créez votre premier dossier de pré-contrôle.'
          }
          action={
            <Link to="/app/dossiers/new" className="btn-primary">
              Créer un dossier
            </Link>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2" data-testid="dossier-list">
            {items.map((d) => (
              <DossierCard key={d.id} dossier={d} />
            ))}
          </div>
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
