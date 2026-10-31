import type { AlertSeverity } from '@/types/models';
import { useTranslation } from '@/i18n';

const STYLES: Record<AlertSeverity, string> = {
  critical: 'bg-red-50 text-red-800 border-red-300',
  high: 'bg-orange-50 text-orange-800 border-orange-300',
  medium: 'bg-amber-50 text-amber-800 border-amber-300',
  low: 'bg-slate-100 text-slate-700 border-slate-300',
};

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const { t } = useTranslation();
  return (
    <span
      data-testid="severity-badge"
      data-severity={severity}
      className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STYLES[severity]}`}
    >
      {t('severity.label', { value: t(`severity.${severity}`) })}
    </span>
  );
}
