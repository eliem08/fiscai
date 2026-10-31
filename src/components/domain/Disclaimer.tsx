import { ShieldCheck } from 'lucide-react';
import { useTranslation } from '@/i18n';

export function Disclaimer() {
  const { t } = useTranslation();
  return (
    <aside
      className="flex items-start gap-3 rounded-xl border border-brand-200 bg-brand-50/60 p-4 text-sm text-brand-900"
      data-testid="legal-disclaimer"
    >
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden="true" />
      <p>{t('legal.disclaimer')}</p>
    </aside>
  );
}
