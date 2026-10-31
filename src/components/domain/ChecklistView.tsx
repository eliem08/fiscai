import { CheckCircle2, FileQuestion, ShieldAlert, XCircle } from 'lucide-react';
import type { ChecklistItem, CheckStatus } from '@/types/models';
import { useTranslation } from '@/i18n';

const ICONS: Record<CheckStatus, { icon: JSX.Element; cls: string }> = {
  passed: { icon: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />, cls: 'text-emerald-800' },
  failed: { icon: <XCircle className="h-4 w-4 text-red-600" aria-hidden="true" />, cls: 'text-red-800' },
  needs_review: { icon: <ShieldAlert className="h-4 w-4 text-amber-600" aria-hidden="true" />, cls: 'text-amber-800' },
  missing: { icon: <FileQuestion className="h-4 w-4 text-orange-600" aria-hidden="true" />, cls: 'text-orange-800' },
};

export function ChecklistView({ items }: { items: ChecklistItem[] }) {
  const { t } = useTranslation();
  return (
    <ul className="space-y-3" data-testid="checklist">
      {items.map((item) => {
        const meta = ICONS[item.status];
        return (
          <li key={item.id} className="card p-4" data-check-status={item.status}>
            <div className="flex items-center gap-2">
              {meta.icon}
              <span className="font-medium text-slate-900">{item.label}</span>
              <span className={`ml-auto text-xs font-semibold ${meta.cls}`}>
                {t(`check.${item.status}`)}
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">{item.detail}</p>
            {item.recommendedAction && (
              <p className="mt-1 text-sm text-slate-500">
                <span className="font-medium">{t('common.actionLabel')} :</span>{' '}
                {item.recommendedAction}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
