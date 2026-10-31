import { describe, expect, it } from 'vitest';
import { guardSqlQuery, READ_ONLY_MESSAGE } from './sqlGuard';

describe('NLU-to-SQL safety guard', () => {
  it('allows plain SELECT queries', () => {
    expect(guardSqlQuery('SELECT * FROM dossiers WHERE statut = @s').allowed).toBe(true);
    expect(guardSqlQuery('select id, titre from dossiers').allowed).toBe(true);
    expect(guardSqlQuery('WITH t AS (SELECT 1 AS n) SELECT n FROM t').allowed).toBe(true);
  });

  it.each([
    'DELETE FROM dossiers',
    'DROP TABLE dossiers',
    'UPDATE dossiers SET statut = 1',
    'INSERT INTO dossiers VALUES (1)',
    'ALTER TABLE dossiers ADD c INT',
    'TRUNCATE TABLE dossiers',
    'EXEC sp_who',
    'MERGE INTO dossiers USING x ON 1=1',
  ])('blocks dangerous operation: %s', (query) => {
    const res = guardSqlQuery(query);
    expect(res.allowed).toBe(false);
    expect(res.reason).toContain(READ_ONLY_MESSAGE);
  });

  it('blocks stacked statements hiding a mutation after a SELECT', () => {
    const res = guardSqlQuery('SELECT 1; DROP TABLE dossiers');
    expect(res.allowed).toBe(false);
    expect(res.blockedKeyword).toBe('DROP');
  });

  it('does not false-positive on keywords inside string literals', () => {
    const res = guardSqlQuery("SELECT * FROM alerts WHERE title = 'please update the file'");
    expect(res.allowed).toBe(true);
  });

  it('rejects empty queries', () => {
    expect(guardSqlQuery('   ').allowed).toBe(false);
  });

  it('exposes the read-only user message', () => {
    expect(READ_ONLY_MESSAGE).toBe('Mode lecture seule activé pour protéger vos données.');
  });
});
