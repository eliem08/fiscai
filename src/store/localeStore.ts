import { create } from 'zustand';

export type Locale = 'fr' | 'en';

const STORAGE_KEY = 'fiscai_lang';

function readInitialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'fr' || stored === 'en') return stored;
  } catch {
    // localStorage unavailable (SSR/tests): fall through to default.
  }
  return 'fr';
}

interface LocaleState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const useLocaleStore = create<LocaleState>((set) => ({
  locale: readInitialLocale(),
  setLocale(locale) {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
      document.documentElement.lang = locale;
    } catch {
      // ignore persistence failures
    }
    set({ locale });
  },
}));

/** Non-reactive read, for use inside services / non-component code. */
export function getLocale(): Locale {
  return useLocaleStore.getState().locale;
}
