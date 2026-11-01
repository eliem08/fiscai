import { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  ShieldCheck,
  ShieldAlert,
  FileCheck,
  Scale,
  Hash,
  User,
  Calendar,
} from 'lucide-react';

export interface ApprovalWorkRequest {
  id: string;
  client_entity_id: string;
  legal_name: string;
  period_code: string;
  status: string;
  prepared_by: string;
  prepared_by_name: string;
  requested_at: string;
  subject_hash: string;
  proposals_count: number;
  total_debit_mad: number;
  total_credit_mad: number;
  open_blocking_issues_count: number;
  open_warning_issues_count: number;
  unacknowledged_review_issues_count?: number;
  single_person_policy?: boolean;
}

export interface ReviewIssueItem {
  id: string;
  code: string;
  status: string;
  resolution?: string;
  resolution_note?: string;
}

export interface CurrentReviewer {
  user_id: string;
  full_name: string;
  role: string;
  professional_title?: 'expert_comptable' | 'comptable_agree' | null;
  professional_registration_no?: string | null;
}

export interface ApprovalScreenProps {
  workRequest: ApprovalWorkRequest;
  reviewer: CurrentReviewer;
  reviewIssues?: ReviewIssueItem[];
  onApprove: (reason: string, subjectHash: string) => Promise<void>;
  onReject: (reason: string) => Promise<void>;
  onAcknowledgeIssue?: (issueId: string, note: string) => Promise<void>;
  isLoading?: boolean;
}

export function ApprovalScreen({
  workRequest,
  reviewer,
  reviewIssues = [],
  onApprove,
  onReject,
  onAcknowledgeIssue,
  isLoading = false,
}: ApprovalScreenProps) {
  const [rejectReason, setRejectReason] = useState('');
  const approveReason = 'Dossier complet, équilibré et contrôlé.';
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [ackIssueId, setAckIssueId] = useState<string | null>(null);
  const [ackNote, setAckNote] = useState('');

  // Quality checks
  const isBalanced = Math.abs(workRequest.total_debit_mad - workRequest.total_credit_mad) < 0.005;
  const hasNoBlockingIssues = workRequest.open_blocking_issues_count === 0;
  const unackCount = workRequest.unacknowledged_review_issues_count ?? 0;
  const hasNoUnackReviewIssues = unackCount === 0;
  const hasProposals = workRequest.proposals_count > 0;
  const qualityGatePassed = isBalanced && hasNoBlockingIssues && hasNoUnackReviewIssues && hasProposals;

  // Segregation of duties & professional registration check
  const isPreparer = reviewer.user_id === workRequest.prepared_by;
  const isPreparerBlocked = isPreparer && !workRequest.single_person_policy;
  const hasProfessionalTitle =
    reviewer.professional_title === 'expert_comptable' ||
    reviewer.professional_title === 'comptable_agree';
  const hasRegistrationNo = Boolean(
    reviewer.professional_registration_no && reviewer.professional_registration_no.trim() !== '',
  );
  const canApprove = qualityGatePassed && !isPreparerBlocked && hasProfessionalTitle && hasRegistrationNo;

  const handleApprove = async () => {
    if (!canApprove) return;
    await onApprove(approveReason, workRequest.subject_hash);
    setToastMessage('Dossier validé');
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) return;
    await onReject(rejectReason);
    setShowRejectModal(false);
    setToastMessage('Dossier refusé');
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg bg-emerald-50 p-4 border border-emerald-200 text-emerald-800 flex items-center gap-2"
        >
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          <span className="font-medium text-sm">{toastMessage}</span>
        </div>
      )}

      {/* Header & Dossier Details */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                Période {workRequest.period_code}
              </span>
              <span className="text-xs text-slate-500">Dossier mensuel</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mt-1">{workRequest.legal_name}</h1>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-600">
            <div className="flex items-center gap-1.5">
              <User className="h-4 w-4 text-slate-400" />
              <span>Préparé par {workRequest.prepared_by_name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4 text-slate-400" />
              <span>{workRequest.requested_at}</span>
            </div>
          </div>
        </div>

        {/* Cryptographic Subject Hash */}
        <div className="mt-4 flex items-center gap-2 text-xs font-mono bg-slate-50 p-3 rounded-lg border border-slate-200">
          <Hash className="h-4 w-4 text-slate-500 shrink-0" />
          <span className="text-slate-600 shrink-0">Empreinte SHA-256 du dossier :</span>
          <span className="text-slate-900 truncate" title={workRequest.subject_hash}>
            {workRequest.subject_hash}
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Écritures</span>
            <FileCheck className="h-5 w-5 text-indigo-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{workRequest.proposals_count}</p>
          <span className="text-xs text-slate-500 mt-1 block">Propositions comptables</span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Total Débit</span>
            <Scale className="h-5 w-5 text-slate-400" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            {workRequest.total_debit_mad.toLocaleString('fr-FR', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}{' '}
            <span className="text-sm font-normal text-slate-500">MAD</span>
          </p>
          <span className="text-xs text-slate-500 mt-1 block">Montant brut débit</span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Total Crédit</span>
            <Scale className="h-5 w-5 text-slate-400" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">
            {workRequest.total_credit_mad.toLocaleString('fr-FR', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}{' '}
            <span className="text-sm font-normal text-slate-500">MAD</span>
          </p>
          <span className="text-xs text-slate-500 mt-1 block">Montant brut crédit</span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Équilibre</span>
            {isBalanced ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            ) : (
              <XCircle className="h-5 w-5 text-rose-500" />
            )}
          </div>
          <p
            className={`text-xl font-bold mt-2 ${isBalanced ? 'text-emerald-700' : 'text-rose-700'}`}
          >
            {isBalanced ? 'Équilibré' : 'Déséquilibré'}
          </p>
          <span className="text-xs text-slate-500 mt-1 block">
            Écart :{' '}
            {Math.abs(workRequest.total_debit_mad - workRequest.total_credit_mad).toFixed(2)} MAD
          </span>
        </div>
      </div>

      {/* Quality Gate Status Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900">Contrôle de qualité préalable</h2>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div
            className={`p-4 rounded-lg border flex items-start gap-3 ${
              hasNoBlockingIssues
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50/50 border-rose-200 text-rose-900'
            }`}
          >
            {hasNoBlockingIssues ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="font-semibold text-sm">Anomalies bloquantes</p>
              <p className="text-xs mt-1 text-slate-600">
                {hasNoBlockingIssues
                  ? 'Aucune anomalie bloquante ouverte.'
                  : `${workRequest.open_blocking_issues_count} anomalie(s) bloquante(s) non résolue(s).`}
              </p>
            </div>
          </div>

          <div
            className={`p-4 rounded-lg border flex items-start gap-3 ${
              hasNoUnackReviewIssues
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                : 'bg-amber-50/50 border-amber-200 text-amber-900'
            }`}
          >
            {hasNoUnackReviewIssues ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="font-semibold text-sm">Anomalies de revue</p>
              <p className="text-xs mt-1 text-slate-600">
                {hasNoUnackReviewIssues
                  ? 'Toutes les anomalies de revue sont acquittées ou résolues.'
                  : `${unackCount} anomalie(s) de revue en attente d'acquittement.`}
              </p>
            </div>
          </div>

          <div
            className={`p-4 rounded-lg border flex items-start gap-3 ${
              isBalanced
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50/50 border-rose-200 text-rose-900'
            }`}
          >
            {isBalanced ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="font-semibold text-sm">Équilibre de la balance</p>
              <p className="text-xs mt-1 text-slate-600">
                {isBalanced
                  ? 'Débit = Crédit au centime près.'
                  : 'Déséquilibre constaté entre débits et crédits.'}
              </p>
            </div>
          </div>

          <div
            className={`p-4 rounded-lg border flex items-start gap-3 ${
              hasProposals
                ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50/50 border-rose-200 text-rose-900'
            }`}
          >
            {hasProposals ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="font-semibold text-sm">Propositions comptables</p>
              <p className="text-xs mt-1 text-slate-600">
                {hasProposals
                  ? `${workRequest.proposals_count} écritures prêtes pour validation.`
                  : 'Le dossier ne contient aucune proposition.'}
              </p>
            </div>
          </div>
        </div>

        {/* Segregation of Duties & Professional Title Warning */}
        {isPreparer && !workRequest.single_person_policy && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 flex items-start gap-3 text-amber-900">
            <ShieldAlert className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">Ségrégation des fonctions requise</p>
              <p className="text-xs mt-1 text-amber-800">
                Vous avez préparé ce dossier. Conformément aux règles de contrôle interne, un
                dossier doit être validé par un réviseur distinct à défaut de politique dérogatoire.
              </p>
            </div>
          </div>
        )}

        {isPreparer && workRequest.single_person_policy && (
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 flex items-start gap-3 text-blue-900">
            <ShieldCheck className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">Politique dérogatoire active</p>
              <p className="text-xs mt-1 text-blue-800">
                Ce dossier autorise l'auto-approbation par un professionnel inscrit qualifié.
              </p>
            </div>
          </div>
        )}

        {/* Review Issues Acknowledgement UI */}
        {reviewIssues.filter((i) => i.status !== 'resolved' && i.status !== 'waived').length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-4 space-y-3">
            <p className="text-sm font-semibold text-amber-900">
              Anomalies de revue nécessitant un acquittement avant validation :
            </p>
            <div className="space-y-2">
              {reviewIssues
                .filter((i) => i.status !== 'resolved' && i.status !== 'waived')
                .map((issue) => (
                  <div
                    key={issue.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-white rounded-lg border border-amber-200"
                  >
                    <div>
                      <span className="font-mono text-xs font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded">
                        {issue.code}
                      </span>
                      <p className="text-xs text-slate-600 mt-1">
                        Anomalie de revue en attente de justification.
                      </p>
                    </div>
                    {ackIssueId === issue.id ? (
                      <div className="flex items-center gap-2 w-full sm:w-auto">
                        <input
                          type="text"
                          placeholder="Motif d'acceptation..."
                          value={ackNote}
                          onChange={(e) => setAckNote(e.target.value)}
                          className="text-xs px-2.5 py-1.5 border border-slate-300 rounded-md flex-1 sm:w-60"
                        />
                        <button
                          type="button"
                          onClick={async () => {
                            if (!ackNote.trim() || !onAcknowledgeIssue) return;
                            await onAcknowledgeIssue(issue.id, ackNote.trim());
                            setAckIssueId(null);
                            setAckNote('');
                            setToastMessage('Anomalie de revue acquittée');
                          }}
                          className="px-3 py-1.5 text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white rounded-md"
                        >
                          Confirmer
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setAckIssueId(null);
                            setAckNote('');
                          }}
                          className="px-2 py-1.5 text-xs text-slate-500 hover:text-slate-700"
                        >
                          Annuler
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setAckIssueId(issue.id)}
                        className="px-3 py-1.5 text-xs font-medium text-amber-800 bg-amber-100 hover:bg-amber-200 rounded-md border border-amber-300"
                      >
                        Acquitter l'anomalie
                      </button>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}

        {(!hasProfessionalTitle || !hasRegistrationNo) && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 flex items-start gap-3 text-amber-900">
            <ShieldCheck className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">Titre professionnel requis</p>
              <p className="text-xs mt-1 text-amber-800">
                La validation définitive requiert un titre d'expert-comptable ou de comptable agréé
                avec un numéro d'inscription à l'ordre valide.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Reviewer Action Bar */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-900">Décision du réviseur</p>
          <p className="text-xs text-slate-500">
            La validation fige irrévocablement les écritures et autorise la génération des exports.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => setShowRejectModal(true)}
            disabled={isLoading}
            className="flex-1 sm:flex-none px-4 py-2.5 rounded-lg border border-rose-300 text-rose-700 bg-rose-50 hover:bg-rose-100 font-medium text-sm transition-colors disabled:opacity-50"
          >
            Refuser le dossier
          </button>

          <button
            type="button"
            onClick={handleApprove}
            disabled={!canApprove || isLoading}
            className="flex-1 sm:flex-none px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <CheckCircle2 className="h-4 w-4" />
            <span>Valider le dossier</span>
          </button>
        </div>
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Motif du refus</h3>
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                &times;
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Précisez la raison pour laquelle ce dossier est renvoyé au préparateur.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Ex : Écart non justifié sur le compte 6111..."
              className="w-full h-28 rounded-lg border border-slate-300 p-3 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
            />
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={!rejectReason.trim() || isLoading}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium disabled:opacity-50"
              >
                Confirmer le refus
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
