import { fr } from '@/i18n/fr';

// Label maps derived from the French reference catalog. UI components should
// prefer the reactive `useTranslation()` hook; these are kept for non-UI code
// (report generation, tests) and default to French.
export const APP_NAME = fr['common.appName'];
export const LEGAL_DISCLAIMER = fr['legal.disclaimer'];
export const PRIVACY_NOTICE = fr['legal.privacy'];

export const RISK_LABELS: Record<string, string> = {
  low: fr['risk.low'],
  medium: fr['risk.medium'],
  high: fr['risk.high'],
  critical: fr['risk.critical'],
};

export const SEVERITY_LABELS: Record<string, string> = {
  critical: fr['severity.critical'],
  high: fr['severity.high'],
  medium: fr['severity.medium'],
  low: fr['severity.low'],
};

export const DOSSIER_STATUS_LABELS: Record<string, string> = {
  draft: fr['dossierStatus.draft'],
  analyzing: fr['dossierStatus.analyzing'],
  analyzed: fr['dossierStatus.analyzed'],
  needs_review: fr['dossierStatus.needs_review'],
  reviewed: fr['dossierStatus.reviewed'],
  issue: fr['dossierStatus.issue'],
};

export const DOSSIER_TYPE_LABELS: Record<string, string> = {
  import: fr['dossierType.import'],
  export: fr['dossierType.export'],
  fiscal: fr['dossierType.fiscal'],
};

export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  commercial_invoice: fr['docType.commercial_invoice'],
  packing_list: fr['docType.packing_list'],
  transport_document: fr['docType.transport_document'],
  certificate_origin: fr['docType.certificate_origin'],
  customs_declaration: fr['docType.customs_declaration'],
  vat_declaration: fr['docType.vat_declaration'],
  other: fr['docType.other'],
};

export const ALERT_STATUS_LABELS: Record<string, string> = {
  open: fr['alertStatus.open'],
  in_review: fr['alertStatus.in_review'],
  resolved: fr['alertStatus.resolved'],
};
