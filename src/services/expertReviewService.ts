import type { Dossier, ExpertReview } from '@/types/models';
import { getDb, delay, persist, ServiceError } from './db';
import { auditLogService, type AuditContext } from './auditLogService';
import { generateId } from '@/lib/id';
import { sanitizeText } from '@/lib/sanitize';

export interface ReviewInput {
  dossierId: string;
  decision: ExpertReview['decision'];
  comment: string;
}

export const expertReviewService = {
  async listAwaiting(organizationId: string): Promise<Dossier[]> {
    await delay(0.5);
    const db = getDb();
    return db.dossiers.filter(
      (d) => d.organizationId === organizationId && d.status === 'needs_review',
    );
  },

  async listReviews(organizationId: string): Promise<ExpertReview[]> {
    await delay(0.5);
    const db = getDb();
    return db.expertReviews.filter((r) => r.organizationId === organizationId);
  },

  async submit(ctx: AuditContext, input: ReviewInput): Promise<ExpertReview> {
    const comment = sanitizeText(input.comment, 1000);
    if (!comment || comment.length < 10) {
      throw new ServiceError(
        'VALIDATION',
        'Le commentaire expert est obligatoire (10 caractères minimum).',
        'Décrivez votre décision pour la piste d’audit.',
      );
    }
    if (!input.decision) throw new ServiceError('VALIDATION', 'Une décision est requise.');
    await delay();
    const db = getDb();
    const dossier = db.dossiers.find(
      (d) => d.id === input.dossierId && d.organizationId === ctx.user.organizationId,
    );
    if (!dossier) throw new ServiceError('NOT_FOUND', 'Dossier introuvable.');

    const review: ExpertReview = {
      id: generateId('rev'),
      organizationId: ctx.user.organizationId,
      dossierId: input.dossierId,
      expertId: ctx.user.id,
      expertName: ctx.user.name,
      decision: input.decision,
      comment,
      createdAt: new Date().toISOString(),
    };
    db.expertReviews.unshift(review);
    dossier.status = input.decision === 'validated' ? 'reviewed' : 'issue';
    dossier.updatedAt = review.createdAt;
    persist();
    auditLogService.record(
      ctx,
      'expert_review.submitted',
      'dossier',
      input.dossierId,
      `Revue experte « ${input.decision} » soumise par ${ctx.user.name} : ${comment.slice(0, 120)}`,
    );
    return review;
  },
};
