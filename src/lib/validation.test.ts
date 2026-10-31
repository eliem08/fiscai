import { describe, expect, it } from 'vitest';
import {
  MAX_FILE_SIZE_BYTES,
  validateDossierForm,
  validateLoginForm,
  validateUploadFile,
} from './validation';

describe('validateDossierForm', () => {
  const valid = { title: 'Import test', clientName: 'Client SARL', type: 'import' as const };

  it('accepts a valid form', () => {
    expect(validateDossierForm(valid).valid).toBe(true);
  });

  it('requires a title', () => {
    const res = validateDossierForm({ ...valid, title: '' });
    expect(res.valid).toBe(false);
    expect(res.errors.some((e) => e.field === 'title')).toBe(true);
  });

  it('requires a client name and a type', () => {
    const res = validateDossierForm({ title: 'Ok ok', clientName: '', type: '' });
    expect(res.errors.map((e) => e.field)).toEqual(expect.arrayContaining(['clientName', 'type']));
  });

  it('rejects malformed BADR references', () => {
    const res = validateDossierForm({ ...valid, referenceBadr: '!!' });
    expect(res.errors.some((e) => e.field === 'referenceBadr')).toBe(true);
  });
});

describe('validateLoginForm', () => {
  it('accepts valid credentials shape', () => {
    expect(validateLoginForm('demo@fiscai.ma', 'Demo1234!').valid).toBe(true);
  });
  it('rejects bad email and short password', () => {
    const res = validateLoginForm('not-an-email', 'short');
    expect(res.errors.map((e) => e.field)).toEqual(expect.arrayContaining(['email', 'password']));
  });
});

describe('validateUploadFile (secure upload)', () => {
  it('accepts an allowed PDF under the size limit', () => {
    expect(
      validateUploadFile({ name: 'facture.pdf', size: 500_000, type: 'application/pdf' }).valid,
    ).toBe(true);
  });

  it('rejects disallowed extensions (whitelist)', () => {
    const res = validateUploadFile({
      name: 'malware.exe',
      size: 1000,
      type: 'application/octet-stream',
    });
    expect(res.valid).toBe(false);
    expect(res.reason).toMatch(/non supporté/);
  });

  it('rejects mismatched MIME types', () => {
    const res = validateUploadFile({ name: 'facture.pdf', size: 1000, type: 'text/javascript' });
    expect(res.valid).toBe(false);
  });

  it('rejects files above 10 MB', () => {
    const res = validateUploadFile({
      name: 'gros.pdf',
      size: MAX_FILE_SIZE_BYTES + 1,
      type: 'application/pdf',
    });
    expect(res.valid).toBe(false);
    expect(res.reason).toMatch(/volumineux/);
  });

  it('rejects empty files', () => {
    expect(validateUploadFile({ name: 'vide.pdf', size: 0, type: 'application/pdf' }).valid).toBe(
      false,
    );
  });
});
