import type { DossierStatus } from '@/types/models';
import { useTranslation } from '@/i18n';

const STYLES: Record<DossierStatus, string> = {
  draft: 'bg-slate-100 text-slate-700 border-slate-300',
  analyzing: 'bg-sky-50 text-sky-800 border-sky-300',
  analyzed: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  needs_review: 'bg-amber-50 text-amber-800 border-amber-300',
  reviewed: 'bg-brand-50 text-brand-800 border-brand-200',
  issue: 'bg-red-50 text-red-800 border-red-300',
};

export function StatusBadge({ status }: { status: DossierStatus }) {
  const { t } = useTranslation();
  return (
    <span
      data-testid="status-badge"
      data-status={status}
      className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STYLES[status]}`}
    >
      {t(`dossierStatus.${status}`)}
    </span>
  );
}
