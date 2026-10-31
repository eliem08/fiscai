import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FileText, Play, Trash2 } from 'lucide-react';
import type { AnalysisResult, DocumentFile, DocumentType, Dossier } from '@/types/models';
import { dossierService } from '@/services/dossierService';
import { documentService } from '@/services/documentService';
import { aiAnalysisService, AGENT_PIPELINE, type AgentStep } from '@/services/aiAnalysisService';
import { reportService } from '@/services/reportService';
import { useCurrentUser } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { DOCUMENT_TYPE_LABELS, DOSSIER_TYPE_LABELS } from '@/lib/constants';
import { formatBytes, formatDate } from '@/lib/format';
import { StatusBadge } from '@/components/domain/StatusBadge';
import { RiskBadge } from '@/components/domain/RiskBadge';
import { UploadZone } from '@/components/domain/UploadZone';
import { ChecklistView } from '@/components/domain/ChecklistView';
import { AgentCard } from '@/components/domain/AgentCard';
import { Disclaimer } from '@/components/domain/Disclaimer';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';

export function DossierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const user = useCurrentUser();
  const navigate = useNavigate();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [documents, setDocuments] = useState<DocumentFile[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<{ step: AgentStep; index: number } | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [confirmPartial, setConfirmPartial] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentFile | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [tab, setTab] = useState<'results' | 'checklist' | 'questions' | 'agents'>('results');
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    if (!user || !id) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [d, docs, ana] = await Promise.all([
        dossierService.get(user.organizationId, id),
        documentService.listByDossier(user.organizationId, id),
        aiAnalysisService.getLatest(user.organizationId, id),
      ]);
      setDossier(d);
      setDocuments(docs);
      setAnalysis(ana);
    } catch (e) {
      setLoadError(e);
    } finally {
      setLoading(false);
    }
  }, [user, id]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  async function handleUpload(file: File, documentType: DocumentType) {
    if (!user || !id) return;
    await documentService.upload(
      { user },
      { dossierId: id, name: file.name, size: file.size, mimeType: file.type, documentType },
    );
    toast('success', `Document « ${file.name} » envoyé.`);
    setDocuments(await documentService.listByDossier(user.organizationId, id));
  }

  async function handleDeleteDocument() {
    if (!user || !deleteTarget || !id) return;
    try {
      await documentService.remove({ user }, deleteTarget.id);
      toast('info', `Document « ${deleteTarget.name} » supprimé.`);
      setDocuments(await documentService.listByDossier(user.organizationId, id));
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Suppression impossible.');
    } finally {
      setDeleteTarget(null);
    }
  }

  async function runAnalysis() {
    if (!user || !id) return;
    setConfirmPartial(false);
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const result = await aiAnalysisService.run({ user }, id, (step, index) =>
        setAnalysisStep({ step, index }),
      );
      setAnalysis(result);
      setDossier(await dossierService.get(user.organizationId, id));
      setTab('results');
      toast('success', `Analyse terminée : score global ${result.scores.overall}/100.`);
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : 'L’analyse a échoué.');
    } finally {
      setAnalyzing(false);
      setAnalysisStep(null);
    }
  }

  function handleLaunchClick() {
    const hasInvoice = documents.some((d) => d.type === 'commercial_invoice');
    if (documents.length === 0 || !hasInvoice) {
      // Warn but allow partial analysis.
      setConfirmPartial(true);
      return;
    }
    void runAnalysis();
  }

  async function handleGenerateReport() {
    if (!user || !id) return;
    setGeneratingReport(true);
    try {
      const report = await reportService.generate({ user }, id);
      toast('success', 'Rapport généré.');
      navigate(`/app/reports/${report.id}`);
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Génération du rapport impossible.');
    } finally {
      setGeneratingReport(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  if (loadError || !dossier) {
    return (
      <div className="space-y-4">
        <Link to="/app/dossiers" className="btn-secondary inline-flex">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Retour aux dossiers
        </Link>
        <ErrorState
          error={loadError ?? new Error('Dossier introuvable.')}
          title="Impossible de charger ce dossier"
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/app/dossiers"
            className="mb-2 inline-flex items-center gap-1 text-sm text-brand-700 underline"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Dossiers
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">{dossier.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {dossier.clientName} · {DOSSIER_TYPE_LABELS[dossier.type]} · créé le{' '}
            {formatDate(dossier.createdAt)}
            {dossier.referenceBadr ? ` · Réf. ${dossier.referenceBadr}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={dossier.status} />
          {analysis && <RiskBadge level={analysis.scores.level} score={analysis.scores.overall} />}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section aria-label="Documents du dossier" className="space-y-4 lg:col-span-1">
          <h2 className="text-lg font-semibold text-slate-900">Documents ({documents.length})</h2>
          <UploadZone onUpload={handleUpload} disabled={analyzing} />
          {documents.length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="no-documents">
              Aucun document. Ajoutez au minimum la facture commerciale.
            </p>
          ) : (
            <ul className="space-y-2" data-testid="document-list">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="card flex items-center justify-between gap-2 p-3 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-800">{doc.name}</p>
                    <p className="text-xs text-slate-500">
                      {DOCUMENT_TYPE_LABELS[doc.type]} · {formatBytes(doc.sizeBytes)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Supprimer le document ${doc.name}`}
                    onClick={() => setDeleteTarget(doc)}
                    disabled={analyzing}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <button
            type="button"
            className="btn-primary w-full"
            onClick={handleLaunchClick}
            disabled={analyzing}
            data-testid="launch-analysis"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            {analyzing ? 'Analyse en cours…' : 'Lancer l’analyse IA'}
          </button>

          {analyzing && analysisStep && (
            <div
              className="card p-4"
              role="status"
              aria-live="polite"
              data-testid="analysis-progress"
            >
              <Spinner
                label={`Étape ${analysisStep.index + 1}/${AGENT_PIPELINE.length} — ${analysisStep.step.agentName}`}
              />
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-brand-500 transition-all"
                  style={{ width: `${((analysisStep.index + 1) / AGENT_PIPELINE.length) * 100}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-slate-500">{analysisStep.step.description}</p>
            </div>
          )}
          {analysisError && (
            <ErrorState
              error={new Error(analysisError)}
              title="L’analyse a échoué"
              onRetry={() => void runAnalysis()}
            />
          )}
        </section>

        <section aria-label="Résultats d’analyse" className="space-y-4 lg:col-span-2">
          {!analysis ? (
            <div className="card p-8 text-center text-sm text-slate-500" data-testid="no-analysis">
              Aucune analyse pour l’instant. Ajoutez vos documents puis lancez l’analyse IA.
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3" data-testid="score-cards">
                <div className="card p-5 text-center">
                  <p className="text-sm text-slate-500">Score fiscal</p>
                  <p className="mt-1 text-3xl font-bold text-slate-900" data-testid="fiscal-score">
                    {analysis.scores.fiscal}/100
                  </p>
                </div>
                <div className="card p-5 text-center">
                  <p className="text-sm text-slate-500">Score douanier</p>
                  <p className="mt-1 text-3xl font-bold text-slate-900" data-testid="customs-score">
                    {analysis.scores.customs}/100
                  </p>
                </div>
                <div className="card p-5 text-center">
                  <p className="text-sm text-slate-500">Global</p>
                  <div className="mt-2 flex justify-center">
                    <RiskBadge level={analysis.scores.level} score={analysis.scores.overall} />
                  </div>
                </div>
              </div>

              {analysis.lowConfidence && (
                <p
                  className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800"
                  role="alert"
                  data-testid="low-confidence-banner"
                >
                  Résultat à faible confiance : la qualité des documents limite la fiabilité de
                  l’extraction. Vérification humaine indispensable.
                </p>
              )}
              {analysis.partial && (
                <p
                  className="rounded-lg border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700"
                  data-testid="partial-banner"
                >
                  Analyse partielle : des documents requis sont absents.
                </p>
              )}

              <div
                role="tablist"
                aria-label="Sections de l’analyse"
                className="flex flex-wrap gap-2 border-b border-slate-200"
              >
                {(
                  [
                    ['results', 'Constats'],
                    ['checklist', 'Checklist'],
                    ['questions', 'Questions fournisseur'],
                    ['agents', 'Agents'],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={tab === key}
                    className={`border-b-2 px-3 py-2 text-sm font-medium ${
                      tab === key
                        ? 'border-brand-600 text-brand-700'
                        : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                    onClick={() => setTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {tab === 'results' && (
                <ul className="space-y-3" data-testid="findings-list">
                  {analysis.scores.findings.length === 0 ? (
                    <li className="card p-5 text-sm text-emerald-700">
                      Aucune anomalie détectée. Dossier prêt pour revue.
                    </li>
                  ) : (
                    analysis.scores.findings.map((f) => (
                      <li key={f.id} className="card p-4" data-finding={f.code}>
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="font-semibold text-slate-900">{f.title}</h3>
                          <span className="text-xs font-semibold uppercase text-slate-400">
                            {f.domain}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-slate-600">{f.detail}</p>
                        <p className="mt-1 text-sm text-slate-500">
                          <span className="font-medium">Action :</span> {f.recommendedAction}
                        </p>
                      </li>
                    ))
                  )}
                </ul>
              )}
              {tab === 'checklist' && <ChecklistView items={analysis.checklist} />}
              {tab === 'questions' && (
                <ul className="space-y-2" data-testid="supplier-questions">
                  {analysis.supplierQuestions.length === 0 ? (
                    <li className="card p-5 text-sm text-slate-500">
                      Aucune question à transmettre.
                    </li>
                  ) : (
                    analysis.supplierQuestions.map((q, i) => (
                      <li key={i} className="card p-4 text-sm text-slate-700">
                        {i + 1}. {q}
                      </li>
                    ))
                  )}
                </ul>
              )}
              {tab === 'agents' && (
                <div className="grid gap-4 md:grid-cols-2">
                  {analysis.agentRuns.map((run) => (
                    <AgentCard key={run.agentId} run={run} />
                  ))}
                </div>
              )}

              <div className="flex justify-end">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void handleGenerateReport()}
                  disabled={generatingReport}
                  data-testid="generate-report"
                >
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  {generatingReport ? 'Génération…' : 'Générer le rapport'}
                </button>
              </div>
            </>
          )}
          <Disclaimer />
        </section>
      </div>

      <Modal
        open={confirmPartial}
        title="Documents requis manquants"
        onClose={() => setConfirmPartial(false)}
        footer={
          <>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setConfirmPartial(false)}
            >
              Ajouter des documents
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void runAnalysis()}
              data-testid="confirm-partial-analysis"
            >
              Lancer une analyse partielle
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          La facture commerciale est absente du dossier. Vous pouvez lancer une analyse partielle,
          mais le score de risque sera dégradé et le résultat marqué à faible confiance.
        </p>
      </Modal>

      <Modal
        open={!!deleteTarget}
        title="Supprimer ce document ?"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setDeleteTarget(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn-danger"
              onClick={() => void handleDeleteDocument()}
            >
              Supprimer définitivement
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          Le document « {deleteTarget?.name} » sera retiré du dossier. Cette action est journalisée
          dans la piste d’audit.
        </p>
      </Modal>
    </div>
  );
}
