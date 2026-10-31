import type { RiskLevel } from '@/types/models';
import { useTranslation } from '@/i18n';

const STYLES: Record<RiskLevel, string> = {
  low: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  medium: 'bg-amber-50 text-amber-800 border-amber-300',
  high: 'bg-orange-50 text-orange-800 border-orange-300',
  critical: 'bg-red-50 text-red-800 border-red-300',
};

// Text label always accompanies the color (no color-only meaning).
export function RiskBadge({ level, score }: { level: RiskLevel; score?: number }) {
  const { t } = useTranslation();
  return (
    <span
      data-testid="risk-badge"
      data-level={level}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STYLES[level]}`}
    >
      {t(`risk.${level}`)}
      {score !== undefined && <span aria-label={t('risk.scoreAria', { score })}> · {score}/100</span>}
    </span>
  );
}
