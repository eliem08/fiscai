import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';
import { resetDb, setServiceLatency } from '@/services/db';
import { useLocaleStore } from '@/store/localeStore';

// Instant services and a clean seeded database for every test.
setServiceLatency(0);

beforeEach(() => {
  localStorage.clear();
  resetDb();
  // French is the reference locale; keep it stable for tests unless overridden.
  useLocaleStore.setState({ locale: 'fr' });
});

afterEach(() => {
  cleanup();
});
