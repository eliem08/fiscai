import { describe, expect, it, beforeEach } from 'vitest';
import { fr } from './fr';
import { en } from './en';
import { translate, t } from './index';
import { useLocaleStore } from '@/store/localeStore';

describe('i18n catalogs', () => {
  it('French and English catalogs have identical keys (full parity)', () => {
    const frKeys = Object.keys(fr).sort();
    const enKeys = Object.keys(en).sort();
    expect(enKeys).toEqual(frKeys);
  });

  it('has no empty translations in either locale', () => {
    for (const [key, value] of Object.entries(fr)) expect(value, `fr.${key}`).not.toBe('');
    for (const [key, value] of Object.entries(en)) expect(value, `en.${key}`).not.toBe('');
  });

  it('translates the same key differently per locale', () => {
    expect(translate('fr', 'nav.dashboard')).toBe('Tableau de bord');
    expect(translate('en', 'nav.dashboard')).toBe('Dashboard');
  });

  it('interpolates parameters', () => {
    expect(translate('en', 'dossier.documents', { count: 3 })).toBe('Documents (3)');
    expect(translate('fr', 'settings.team', { count: 5 })).toBe('Équipe (5)');
  });

  it('leaves unknown parameters untouched', () => {
    expect(translate('en', 'review.saved', {})).toBe('Review saved for “{title}”.');
  });
});

describe('non-reactive t()', () => {
  beforeEach(() => useLocaleStore.setState({ locale: 'fr' }));

  it('uses the current store locale', () => {
    expect(t('common.save')).toBe('Enregistrer');
    useLocaleStore.getState().setLocale('en');
    expect(t('common.save')).toBe('Save');
  });
});
