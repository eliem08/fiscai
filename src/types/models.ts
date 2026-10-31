// Central typed data models for FiscAI PreClear.

export type Role = 'admin' | 'analyst' | 'expert' | 'viewer';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';
export type AlertStatus = 'open' | 'in_review' | 'resolved';
export type DossierType = 'import' | 'export' | 'fiscal';
export type DossierStatus =
  'draft' | 'analyzing' | 'analyzed' | 'needs_review' | 'reviewed' | 'issue';
export type DocumentType =
  | 'commercial_invoice'
  | 'packing_list'
  | 'transport_document'
  | 'certificate_origin'
  | 'customs_declaration'
  | 'vat_declaration'
  | 'other';
export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'needs_review';
export type CheckStatus = 'passed' | 'failed' | 'needs_review' | 'missing';

export interface Organization {
  id: string;
  name: string;
  ice: string; // Identifiant Commun de l'Entreprise
  city: string;
  plan: 'starter' | 'pro' | 'enterprise';
  createdAt: string;
}

export interface User {
  id: string;
  organizationId: string;
  name: string;
  email: string;
  role: Role;
}

export interface Dossier {
  id: string;
  organizationId: string;
  title: string;
  clientName: string;
  type: DossierType;
  status: DossierStatus;
  description?: string;
  referenceBadr?: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  riskReportId?: string;
}

export interface DocumentFile {
  id: string;
  organizationId: string;
  dossierId: string;
  name: string;
  type: DocumentType;
  mimeType: string;
  sizeBytes: number;
  uploadedBy: string;
  uploadedAt: string;
  status: 'uploaded' | 'extracted' | 'failed';
}

export interface ExtractedField {
  key: string;
  label: string;
  value: string | number | null;
  confidence: number; // 0..1
}

export interface ExtractionResult {
  documentId: string;
  documentType: DocumentType;
  fields: ExtractedField[];
  missingFields: string[];
  confidence: number; // global 0..1
  warnings: string[];
}

export interface Finding {
  id: string;
  domain: 'fiscal' | 'customs' | 'general';
  code: string;
  severity: AlertSeverity;
  title: string;
  detail: string;
  evidence?: string;
  recommendedAction: string;
}

export interface RiskScores {
  fiscal: number; // 0..100, higher = riskier
  customs: number;
  overall: number;
  level: RiskLevel;
  expertReviewRequired: boolean;
  findings: Finding[];
  confidence: number;
}

export interface ChecklistItem {
  id: string;
  label: string;
  status: CheckStatus;
  detail: string;
  recommendedAction?: string;
}

export interface AgentRun {
  agentId: string;
  agentName: string;
  description: string;
  status: AgentStatus;
  confidence: number;
  findings: string[];
  evidence: string[];
  recommendedAction: string;
}

export interface AnalysisResult {
  id: string;
  dossierId: string;
  organizationId: string;
  createdAt: string;
  scores: RiskScores;
  extractions: ExtractionResult[];
  checklist: ChecklistItem[];
  agentRuns: AgentRun[];
  supplierQuestions: string[];
  lowConfidence: boolean;
  partial: boolean;
}

export interface Alert {
  id: string;
  organizationId: string;
  dossierId: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  detail: string;
  createdAt: string;
  updatedAt: string;
}

export interface ReportSection {
  key: string;
  title: string;
  content: string;
}

export interface Report {
  id: string;
  organizationId: string;
  organizationName: string;
  dossierId: string;
  dossierTitle: string;
  clientName: string;
  date: string;
  scores: RiskScores;
  sections: ReportSection[];
  expertReviewStatus: 'pending' | 'validated' | 'correction_required' | 'not_required';
  disclaimer: string;
}

export interface ExpertReview {
  id: string;
  organizationId: string;
  dossierId: string;
  expertId: string;
  expertName: string;
  decision: 'validated' | 'correction_required' | 'rejected';
  comment: string;
  createdAt: string;
}

export interface AuditLogEntry {
  id: string;
  userId: string;
  userName: string;
  organizationId: string;
  action: string;
  entityType: string;
  entityId: string;
  timestamp: string;
  details: string;
  riskLevel?: RiskLevel;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
