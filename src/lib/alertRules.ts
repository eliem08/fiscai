// Alert generation rules: maps analysis findings to alert severities.

import type { Alert, AlertSeverity, Finding } from '@/types/models';
import { generateId } from './id';

const SEVERITY_BY_CODE: Record<string, AlertSeverity> = {
  MISSING_PACKING_LIST: 'critical',
  HS_CODE_UNCERTAIN: 'high',
  MISSING_SUPPLIER_IDENTITY: 'high',
  VAGUE_DESCRIPTION: 'high',
  VAT_MISMATCH: 'medium',
  LOW_EXTRACTION_CONFIDENCE: 'medium',
  NO_DOCUMENTS: 'high',
  MISSING_CERTIFICATE_ORIGIN: 'low',
};

export function severityForFinding(finding: Finding): AlertSeverity {
  return SEVERITY_BY_CODE[finding.code] ?? finding.severity;
}

export function generateAlertsFromFindings(
  findings: Finding[],
  ctx: { organizationId: string; dossierId: string },
): Alert[] {
  const now = new Date().toISOString();
  return findings.map((f) => ({
    id: generateId('alr'),
    organizationId: ctx.organizationId,
    dossierId: ctx.dossierId,
    severity: severityForFinding(f),
    status: 'open',
    title: f.title,
    detail: f.detail,
    createdAt: now,
    updatedAt: now,
  }));
}
