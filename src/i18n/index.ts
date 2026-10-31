import { fr } from './fr';
import { en } from './en';
import { useLocaleStore, type Locale, getLocale } from '@/store/localeStore';

export type TranslationKey = keyof typeof fr;
export type TranslationParams = Record<string, string | number>;

export const catalogs: Record<Locale, Record<TranslationKey, string>> = { fr, en };

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, key) =>
    key in params ? String(params[key]) : match,
  );
}

/** Translate a key for a given locale. Falls back to French, then the key. */
export function translate(
  locale: Locale,
  key: TranslationKey,
  params?: TranslationParams,
): string {
  const template = catalogs[locale][key] ?? catalogs.fr[key] ?? key;
  return interpolate(template, params);
}

/** Non-reactive translation, for services / non-component code. */
export function t(key: TranslationKey, params?: TranslationParams): string {
  return translate(getLocale(), key, params);
}

/** Reactive hook: re-renders the component when the locale changes. */
export function useTranslation() {
  const locale = useLocaleStore((s) => s.locale);
  const setLocale = useLocaleStore((s) => s.setLocale);
  const tt = (key: TranslationKey, params?: TranslationParams) => translate(locale, key, params);
  return { t: tt, locale, setLocale };
}
