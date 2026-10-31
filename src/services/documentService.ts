import type { DocumentFile, DocumentType } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { generateId } from '@/lib/id';
import { sanitizeText } from '@/lib/sanitize';
import { validateUploadFile } from '@/lib/validation';

export interface UploadInput {
  dossierId: string;
  name: string;
  size: number;
  mimeType: string;
  documentType: DocumentType;
}

export const documentService = {
  async listByDossier(organizationId: string, dossierId: string): Promise<DocumentFile[]> {
    await delay(0.5);
    const db = getDb();
    return db.documents.filter(
      (d) => d.organizationId === organizationId && d.dossierId === dossierId,
    );
  },

  async listAll(organizationId: string): Promise<DocumentFile[]> {
    await delay(0.5);
    const db = getDb();
    return [...db.documents.filter((d) => d.organizationId === organizationId)].sort((a, b) =>
      b.uploadedAt.localeCompare(a.uploadedAt),
    );
  },

  async upload(ctx: AuditContext, input: UploadInput): Promise<DocumentFile> {
    const check = validateUploadFile({ name: input.name, size: input.size, type: input.mimeType });
    if (!check.valid) {
      throw new ServiceError(
        'INVALID_FILE',
        check.reason ?? 'Fichier invalide.',
        'Choisissez un fichier PDF, image ou XLSX de moins de 10 Mo.',
      );
    }
    await delay(1.5);
    const db = getDb();
    const dossier = db.dossiers.find(
      (d) => d.id === input.dossierId && d.organizationId === ctx.user.organizationId,
    );
    if (!dossier) throw new ServiceError('NOT_FOUND', 'Dossier introuvable pour cet envoi.');
    const doc: DocumentFile = {
      id: generateId('doc'),
      organizationId: ctx.user.organizationId,
      dossierId: input.dossierId,
      name: sanitizeText(input.name, 180),
      type: input.documentType,
      mimeType: input.mimeType,
      sizeBytes: input.size,
      uploadedBy: ctx.user.id,
      uploadedAt: new Date().toISOString(),
      status: 'uploaded',
    };
    db.documents.push(doc);
    dossier.updatedAt = doc.uploadedAt;
    persist();
    auditLogService.record(
      ctx,
      'document.uploaded',
      'document',
      doc.id,
      `Document « ${doc.name} » ajouté au dossier ${dossier.title}.`,
    );
    return doc;
  },

  async remove(ctx: AuditContext, documentId: string): Promise<void> {
    await delay(0.5);
    const db = getDb();
    const idx = db.documents.findIndex(
      (d) => d.id === documentId && d.organizationId === ctx.user.organizationId,
    );
    if (idx === -1) throw new ServiceError('NOT_FOUND', 'Document introuvable.');
    const [doc] = db.documents.splice(idx, 1);
    persist();
    auditLogService.record(
      ctx,
      'document.deleted',
      'document',
      doc.id,
      `Document « ${doc.name} » supprimé.`,
    );
  },
};
