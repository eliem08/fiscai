import { Globe } from 'lucide-react';
import { useTranslation } from '@/i18n';
import type { Locale } from '@/store/localeStore';

// The interface renders in French or English; the choice is persisted in
// localStorage by the locale store. Arabic can be added later as a new catalog.
const LANGUAGES: { code: Locale; labelKey: 'lang.fr' | 'lang.en' }[] = [
  { code: 'fr', labelKey: 'lang.fr' },
  { code: 'en', labelKey: 'lang.en' },
];

export function LanguageSelector() {
  const { t, locale, setLocale } = useTranslation();
  return (
    <div className="flex items-center gap-1" data-testid="language-selector">
      <Globe className="h-4 w-4 text-slate-400" aria-hidden="true" />
      <label htmlFor="language-select" className="sr-only">
        {t('lang.label')}
      </label>
      <select
        id="language-select"
        className="rounded-lg border-0 bg-transparent py-1 pl-1 pr-6 text-sm text-slate-600 focus:ring-1 focus:ring-brand-500"
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {t(l.labelKey)}
          </option>
        ))}
      </select>
    </div>
  );
}
