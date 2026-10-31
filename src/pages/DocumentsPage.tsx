import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Search } from 'lucide-react';
import type { DocumentFile, DocumentType } from '@/types/models';
import { documentService } from '@/services/documentService';
import { useCurrentUser } from '@/store/authStore';
import { DOCUMENT_TYPE_LABELS } from '@/lib/constants';
import { formatBytes, formatDateTime } from '@/lib/format';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { Pagination } from '@/components/ui/Pagination';

const PAGE_SIZE = 8;

export function DocumentsPage() {
  const user = useCurrentUser();
  const [docs, setDocs] = useState<DocumentFile[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<DocumentType | 'all'>('all');
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    documentService
      .listAll(user.organizationId)
      .then((d) => !cancelled && setDocs(d))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  const filtered = useMemo(() => {
    if (!docs) return [];
    let items = docs;
    if (typeFilter !== 'all') items = items.filter((d) => d.type === typeFilter);
    const q = search.trim().toLowerCase();
    if (q) items = items.filter((d) => d.name.toLowerCase().includes(q));
    return items;
  }, [docs, search, typeFilter]);

  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Bibliothèque de documents</h1>
        <p className="text-sm text-slate-500">
          Tous les documents envoyés dans votre espace de travail.
        </p>
      </div>

      <div className="card flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-52 flex-1">
          <label className="label" htmlFor="doc-search">
            Recherche
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              id="doc-search"
              className="input pl-9"
              placeholder="Nom du fichier…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="doc-type-filter">
            Type
          </label>
          <select
            id="doc-type-filter"
            className="input"
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value as DocumentType | 'all');
              setPage(1);
            }}
          >
            <option value="all">Tous</option>
            {Object.entries(DOCUMENT_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : docs === null ? (
        <div className="space-y-3" aria-busy="true">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Aucun document"
          description="Les documents envoyés depuis vos dossiers apparaîtront ici."
          icon={<FileText className="h-7 w-7" />}
        />
      ) : (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Liste des documents de l’organisation</caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Fichier
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Type
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Taille
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Envoyé le
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Dossier
                  </th>
                </tr>
              </thead>
              <tbody>
                {paged.map((doc) => (
                  <tr
                    key={doc.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                  >
                    <td className="max-w-56 truncate px-4 py-3 font-medium text-slate-800">
                      {doc.name}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{DOCUMENT_TYPE_LABELS[doc.type]}</td>
                    <td className="px-4 py-3 text-slate-600">{formatBytes(doc.sizeBytes)}</td>
                    <td className="px-4 py-3 text-slate-600">{formatDateTime(doc.uploadedAt)}</td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/app/dossiers/${doc.dossierId}`}
                        className="text-brand-700 underline"
                      >
                        Ouvrir
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={filtered.length}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
