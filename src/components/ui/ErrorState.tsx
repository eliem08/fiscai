import { AlertTriangle, RotateCcw } from 'lucide-react';
import { ServiceError } from '@/services/db';
import { useTranslation } from '@/i18n';

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  const { t } = useTranslation();
  const message = error instanceof Error ? error.message : t('error.unknown');
  const action = error instanceof ServiceError ? error.suggestedAction : undefined;
  return (
    <div
      className="card flex flex-col items-center justify-center border-red-200 bg-red-50/50 px-6 py-10 text-center"
      role="alert"
      data-testid="error-state"
    >
      <div className="mb-3 rounded-full bg-red-100 p-3 text-red-600" aria-hidden="true">
        <AlertTriangle className="h-7 w-7" />
      </div>
      <h3 className="text-base font-semibold text-slate-800">{title ?? t('error.title')}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-600">{message}</p>
      {action && <p className="mt-1 max-w-md text-sm text-slate-500">{action}</p>}
      {onRetry && (
        <button type="button" className="btn-secondary mt-4" onClick={onRetry}>
          <RotateCcw className="h-4 w-4" aria-hidden="true" /> {t('common.retry')}
        </button>
      )}
    </div>
  );
}
