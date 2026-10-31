import { Link } from 'react-router-dom';
import type { Alert } from '@/types/models';
import { useTranslation } from '@/i18n';
import { formatDateTime } from '@/lib/format';
import { SeverityBadge } from './SeverityBadge';

interface AlertCardProps {
  alert: Alert;
  onStatusChange?: (status: Alert['status']) => void;
  busy?: boolean;
}

export function AlertCard({ alert, onStatusChange, busy }: AlertCardProps) {
  const { t } = useTranslation();
  return (
    <div className="card p-5" data-testid="alert-card" data-severity={alert.severity}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-900">{alert.title}</h3>
          <p className="mt-1 text-sm text-slate-600">{alert.detail}</p>
        </div>
        <SeverityBadge severity={alert.severity} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <span>
          {t('common.status')} :{' '}
          <strong className="text-slate-600">{t(`alertStatus.${alert.status}`)}</strong> ·{' '}
          {formatDateTime(alert.createdAt)} ·{' '}
          <Link className="text-brand-700 underline" to={`/app/dossiers/${alert.dossierId}`}>
            {t('alerts.seeDossier')}
          </Link>
        </span>
        {onStatusChange && alert.status !== 'resolved' && (
          <div className="flex gap-2">
            {alert.status === 'open' && (
              <button
                type="button"
                className="btn-secondary px-2 py-1 text-xs"
                disabled={busy}
                onClick={() => onStatusChange('in_review')}
              >
                {t('alerts.toReview')}
              </button>
            )}
            <button
              type="button"
              className="btn-primary px-2 py-1 text-xs"
              disabled={busy}
              onClick={() => onStatusChange('resolved')}
            >
              {t('alerts.markResolved')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
