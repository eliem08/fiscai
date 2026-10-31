import { useEffect, useState, type FormEvent } from 'react';
import { ShieldCheck } from 'lucide-react';
import type { AnalysisResult, Dossier, ExpertReview } from '@/types/models';
import { expertReviewService } from '@/services/expertReviewService';
import { aiAnalysisService } from '@/services/aiAnalysisService';
import { useCurrentUser } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { RiskBadge } from '@/components/domain/RiskBadge';
import { Disclaimer } from '@/components/domain/Disclaimer';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { formatDateTime } from '@/lib/format';

export function ExpertReviewPage() {
  const user = useCurrentUser();
  const [awaiting, setAwaiting] = useState<Dossier[] | null>(null);
  const [reviews, setReviews] = useState<ExpertReview[]>([]);
  const [selected, setSelected] = useState<Dossier | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [decision, setDecision] = useState<ExpertReview['decision'] | ''>('');
  const [comment, setComment] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    Promise.all([
      expertReviewService.listAwaiting(user.organizationId),
      expertReviewService.listReviews(user.organizationId),
    ])
      .then(([a, r]) => {
        if (!cancelled) {
          setAwaiting(a);
          setReviews(r);
        }
      })
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  async function selectDossier(d: Dossier) {
    if (!user) return;
    setSelected(d);
    setDecision('');
    setComment('');
    setFormError(null);
    setAnalysis(await aiAnalysisService.getLatest(user.organizationId, d.id));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user || !selected) return;
    setFormError(null);
    if (!decision) {
      setFormError('Veuillez choisir une décision.');
      return;
    }
    if (comment.trim().length < 10) {
      setFormError('Le commentaire expert est obligatoire (10 caractères minimum).');
      return;
    }
    setSaving(true);
    try {
      await expertReviewService.submit({ user }, { dossierId: selected.id, decision, comment });
      toast('success', `Revue enregistrée pour « ${selected.title} ».`);
      setSelected(null);
      setAnalysis(null);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Enregistrement impossible.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Revue experte</h1>
        <p className="text-sm text-slate-500">
          Validation humaine obligatoire des dossiers à risque élevé ou critique avant tout usage
          officiel.
        </p>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />
      ) : awaiting === null ? (
        <div className="space-y-3" aria-busy="true">
          <SkeletonCard />
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <section aria-label="Dossiers en attente de revue">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">
              En attente ({awaiting.length})
            </h2>
            {awaiting.length === 0 ? (
              <EmptyState
                title="Aucun dossier en attente"
                description="Les dossiers à risque élevé apparaîtront ici après analyse."
                icon={<ShieldCheck className="h-7 w-7" />}
              />
            ) : (
              <ul className="space-y-3" data-testid="awaiting-list">
                {awaiting.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => void selectDossier(d)}
                      className={`card w-full p-4 text-left transition hover:border-brand-300 ${
                        selected?.id === d.id ? 'border-brand-500 ring-1 ring-brand-500' : ''
                      }`}
                    >
                      <p className="font-semibold text-slate-900">{d.title}</p>
                      <p className="text-sm text-slate-500">{d.clientName}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {reviews.length > 0 && (
              <div className="mt-6">
                <h3 className="mb-2 text-sm font-semibold text-slate-700">Revues récentes</h3>
                <ul className="space-y-2 text-sm">
                  {reviews.slice(0, 5).map((r) => (
                    <li key={r.id} className="card p-3 text-slate-600">
                      <strong>{r.expertName}</strong> —{' '}
                      {r.decision === 'validated' ? 'Validé' : 'Correction requise'} ·{' '}
                      {formatDateTime(r.createdAt)}
                      <p className="mt-1 text-xs text-slate-500">{r.comment}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section aria-label="Formulaire de revue experte">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Décision</h2>
            {!selected ? (
              <div className="card p-8 text-center text-sm text-slate-500">
                Sélectionnez un dossier en attente pour examiner les constats de l’IA.
              </div>
            ) : (
              <form
                className="card space-y-4 p-6"
                onSubmit={(e) => void handleSubmit(e)}
                noValidate
                data-testid="review-form"
              >
                <div>
                  <p className="font-semibold text-slate-900">{selected.title}</p>
                  {analysis && (
                    <div className="mt-2 flex items-center gap-3 text-sm text-slate-600">
                      <RiskBadge level={analysis.scores.level} score={analysis.scores.overall} />
                      <span>{analysis.scores.findings.length} constat(s) IA</span>
                    </div>
                  )}
                  {analysis && analysis.scores.findings.length > 0 && (
                    <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-slate-600">
                      {analysis.scores.findings.slice(0, 5).map((f) => (
                        <li key={f.id}>{f.title}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <fieldset>
                  <legend className="label">Décision *</legend>
                  <div className="space-y-2">
                    {(
                      [
                        ['validated', 'Dossier validé — conforme pour transmission'],
                        ['correction_required', 'Correction requise — retour au client'],
                        ['rejected', 'Rejeté — dossier non exploitable'],
                      ] as const
                    ).map(([value, label]) => (
                      <label key={value} className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="radio"
                          name="review-decision"
                          value={value}
                          checked={decision === value}
                          onChange={() => setDecision(value)}
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div>
                  <label className="label" htmlFor="review-comment">
                    Commentaire expert * (journalisé)
                  </label>
                  <textarea
                    id="review-comment"
                    className="input"
                    rows={4}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Justifiez votre décision pour la piste d’audit…"
                    aria-invalid={!!formError}
                  />
                </div>

                {formError && (
                  <p
                    role="alert"
                    className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
                    data-testid="review-error"
                  >
                    {formError}
                  </p>
                )}

                <div className="flex justify-end gap-3">
                  <button type="button" className="btn-secondary" onClick={() => setSelected(null)}>
                    Annuler
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={saving}
                    data-testid="submit-review"
                  >
                    {saving ? 'Enregistrement…' : 'Enregistrer la revue'}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}
      <Disclaimer />
    </div>
  );
}
