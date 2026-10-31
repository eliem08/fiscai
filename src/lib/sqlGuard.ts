// NLU-to-SQL safety layer: read-only guard for the future Data Query Agent.
// Only SELECT statements are allowed; every mutating or procedural keyword is blocked.

const BLOCKED_KEYWORDS = [
  'DELETE',
  'DROP',
  'UPDATE',
  'INSERT',
  'ALTER',
  'TRUNCATE',
  'EXEC',
  'EXECUTE',
  'MERGE',
  'GRANT',
  'REVOKE',
  'CREATE',
] as const;

export interface SqlGuardResult {
  allowed: boolean;
  reason?: string;
  blockedKeyword?: string;
}

export const READ_ONLY_MESSAGE = 'Mode lecture seule activé pour protéger vos données.';

export function guardSqlQuery(rawQuery: string): SqlGuardResult {
  const query = rawQuery.trim();
  if (!query) {
    return { allowed: false, reason: 'Requête vide.' };
  }
  // Strip string literals so keywords inside quoted values do not false-positive,
  // then check every statement (protects against "SELECT 1; DROP TABLE x").
  const withoutLiterals = query.replace(/'(?:[^']|'')*'/g, "''").replace(/"(?:[^"]|"")*"/g, '""');
  const statements = withoutLiterals
    .split(';')
    .map((s) => s.trim())
    .filter(Boolean);

  for (const statement of statements) {
    for (const keyword of BLOCKED_KEYWORDS) {
      const pattern = new RegExp(`\\b${keyword}\\b`, 'i');
      if (pattern.test(statement)) {
        return {
          allowed: false,
          blockedKeyword: keyword,
          reason: `${READ_ONLY_MESSAGE} Opération bloquée : ${keyword}.`,
        };
      }
    }
    if (!/^select\b/i.test(statement) && !/^with\b/i.test(statement)) {
      return {
        allowed: false,
        reason: `${READ_ONLY_MESSAGE} Seules les requêtes SELECT sont autorisées.`,
      };
    }
  }
  return { allowed: true };
}
