// Mock persistence layer. All services read/write through this module, so a
// real backend can replace it by swapping the service implementations only.
// Data is kept in memory and mirrored to localStorage when available.

import type {
  Alert,
  AnalysisResult,
  AuditLogEntry,
  DocumentFile,
  Dossier,
  ExpertReview,
  Organization,
  Report,
  User,
} from '@/types/models';
import {
  seedAlerts,
  seedAuditLogs,
  seedDocuments,
  seedDossiers,
  seedOrganizations,
  seedUsers,
} from '@/mocks/seed';

export interface Db {
  organizations: Organization[];
  users: (User & { password: string })[];
  dossiers: Dossier[];
  documents: DocumentFile[];
  analyses: AnalysisResult[];
  alerts: Alert[];
  reports: Report[];
  expertReviews: ExpertReview[];
  auditLogs: AuditLogEntry[];
}

const STORAGE_KEY = 'fiscai_db_v1';

function freshDb(): Db {
  return {
    organizations: structuredClone(seedOrganizations),
    users: structuredClone(seedUsers),
    dossiers: structuredClone(seedDossiers),
    documents: structuredClone(seedDocuments),
    analyses: [],
    alerts: structuredClone(seedAlerts),
    reports: [],
    expertReviews: [],
    auditLogs: structuredClone(seedAuditLogs),
  };
}

let db: Db | null = null;

function storageAvailable(): boolean {
  try {
    return typeof localStorage !== 'undefined';
  } catch {
    return false;
  }
}

export function getDb(): Db {
  if (db) return db;
  if (storageAvailable()) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        db = JSON.parse(raw) as Db;
        return db;
      }
    } catch {
      // Corrupted storage: fall through to a fresh seed.
    }
  }
  db = freshDb();
  persist();
  return db;
}

export function persist(): void {
  if (!db || !storageAvailable()) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    // Quota errors are non-fatal for the mock layer.
  }
}

/** Resets to seed data. Used by tests and the demo "reset workspace" action. */
export function resetDb(): Db {
  db = freshDb();
  persist();
  return db;
}

// --- Simulated network latency -------------------------------------------

let latencyMs = 250;

export function setServiceLatency(ms: number): void {
  latencyMs = ms;
}

export function delay(factor = 1): Promise<void> {
  const ms = latencyMs * factor;
  return ms <= 0 ? Promise.resolve() : new Promise((r) => setTimeout(r, ms));
}

/** Typed service error with a user-facing reason and suggested action. */
export class ServiceError extends Error {
  readonly code: string;
  readonly suggestedAction?: string;
  constructor(code: string, message: string, suggestedAction?: string) {
    super(message);
    this.name = 'ServiceError';
    this.code = code;
    this.suggestedAction = suggestedAction;
  }
}
