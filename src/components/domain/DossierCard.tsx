import { Link } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import type { Dossier } from '@/types/models';
import { useTranslation } from '@/i18n';
import { formatDate } from '@/lib/format';
import { StatusBadge } from './StatusBadge';

export function DossierCard({ dossier }: { dossier: Dossier }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/app/dossiers/${dossier.id}`}
      className="card block p-5 transition hover:border-brand-300 hover:shadow-md"
      data-testid="dossier-card"
      aria-label={t('dossiers.openAria', { title: dossier.title })}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 rounded-lg bg-brand-50 p-2 text-brand-600" aria-hidden="true">
            <FolderOpen className="h-5 w-5" />
          </span>
          <div>
            <h3 className="font-semibold text-slate-900">{dossier.title}</h3>
            <p className="text-sm text-slate-500">
              {dossier.clientName} · {t(`dossierType.${dossier.type}`)}
            </p>
          </div>
        </div>
        <StatusBadge status={dossier.status} />
      </div>
      <p className="mt-3 text-xs text-slate-400">
        {t('dossiers.updatedOn', { date: formatDate(dossier.updatedAt) })}
        {dossier.referenceBadr ? ` · ${t('dossiers.ref', { ref: dossier.referenceBadr })}` : ''}
      </p>
    </Link>
  );
}
