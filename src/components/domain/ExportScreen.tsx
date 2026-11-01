import { useState } from 'react';
import {
  Download,
  FileArchive,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';

export type ExportTarget = 'sage100_csv' | 'sage100_pnm' | 'odoo_csv';

export interface ExportProfileSummary {
  id: string;
  name: string;
  target: ExportTarget;
  encoding: 'cp1252' | 'utf-8';
  verified_round_trip_at?: string | null;
}

export interface ExportResult {
  id: string;
  work_request_id: string;
  client_entity_id: string;
  target: ExportTarget;
  encoding: string;
  status: 'generating' | 'ready' | 'failed';
  file_sha256: string;
  evidence_pack_sha256: string;
  subject_hash: string;
  file_size_bytes?: number;
  evidence_pack_size_bytes?: number;
  created_at: string;
}

export interface ExportScreenProps {
  workRequestId: string;
  approvalId: string;
  clientName: string;
  periodCode: string;
  approvedSubjectHash: string;
  availableProfiles: ExportProfileSummary[];
  currentExport?: ExportResult | null;
  onGenerateExport: (target: ExportTarget, profileId?: string) => Promise<ExportResult>;
  onDownloadFile: (exportId: string) => Promise<void>;
  onDownloadEvidencePack: (exportId: string) => Promise<void>;
  isLoading?: boolean;
}

export function ExportScreen({
  workRequestId: _workRequestId,
  approvalId: _approvalId,
  clientName,
  periodCode,
  approvedSubjectHash,
  availableProfiles,
  currentExport: initialExport = null,
  onGenerateExport,
  onDownloadFile,
  onDownloadEvidencePack,
  isLoading = false,
}: ExportScreenProps) {
  const [selectedTarget, setSelectedTarget] = useState<ExportTarget>('sage100_csv');
  const [exportData, setExportData] = useState<ExportResult | null>(initialExport);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const activeProfile = availableProfiles.find((p) => p.target === selectedTarget);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setErrorMessage(null);
    try {
      const res = await onGenerateExport(selectedTarget, activeProfile?.id);
      setExportData(res);
      setToastMessage('Export comptable et pack de preuves générés avec succès.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : null;
      setErrorMessage(
        msg ||
          "Le dossier a changé depuis la validation. Demandez une nouvelle validation.",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const isHashMatching =
    exportData && exportData.subject_hash.toLowerCase() === approvedSubjectHash.toLowerCase();

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

      {/* Error Banner */}
      {errorMessage && (
        <div
          role="alert"
          className="rounded-lg bg-rose-50 p-4 border border-rose-200 text-rose-800 flex items-center gap-2"
        >
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <span className="font-medium text-sm">{errorMessage}</span>
        </div>
      )}

      {/* Header & Dossier Context */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
                Dossier validé
              </span>
              <span className="text-xs text-slate-500">Période {periodCode}</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mt-1">{clientName}</h1>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono bg-slate-50 p-2.5 rounded-lg border border-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
            <span className="text-slate-600">Empreinte validée :</span>
            <span className="text-slate-900 font-semibold truncate max-w-xs" title={approvedSubjectHash}>
              {approvedSubjectHash.slice(0, 16)}...
            </span>
          </div>
        </div>

        {/* Target Profile Selection */}
        <div className="mt-6 space-y-4">
          <label className="block text-sm font-semibold text-slate-900">
            Format du progiciel comptable
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              type="button"
              onClick={() => setSelectedTarget('sage100_csv')}
              className={`p-4 rounded-xl border text-left transition-all ${
                selectedTarget === 'sage100_csv'
                  ? 'border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 text-sm">Sage 100 (CSV)</span>
                <FileSpreadsheet className="h-5 w-5 text-indigo-600" />
              </div>
              <p className="text-xs text-slate-500 mt-1">CP1252, délimiteur point-virgule, CRLF</p>
            </button>

            <button
              type="button"
              onClick={() => setSelectedTarget('sage100_pnm')}
              className={`p-4 rounded-xl border text-left transition-all ${
                selectedTarget === 'sage100_pnm'
                  ? 'border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 text-sm">Sage 100 (PNM)</span>
                <FileSpreadsheet className="h-5 w-5 text-indigo-600" />
              </div>
              <p className="text-xs text-slate-500 mt-1">Format natif PNM, CP1252, CRLF</p>
            </button>

            <button
              type="button"
              onClick={() => setSelectedTarget('odoo_csv')}
              className={`p-4 rounded-xl border text-left transition-all ${
                selectedTarget === 'odoo_csv'
                  ? 'border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 text-sm">Odoo (CSV)</span>
                <FileSpreadsheet className="h-5 w-5 text-indigo-600" />
              </div>
              <p className="text-xs text-slate-500 mt-1">UTF-8, écritures multi-lignes, CRLF</p>
            </button>
          </div>

          {activeProfile?.verified_round_trip_at ? (
            <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
              <CheckCircle2 className="h-4 w-4" />
              <span>
                Aller-retour vérifié avec succès sur le logiciel pilote le{' '}
                {new Date(activeProfile.verified_round_trip_at).toLocaleDateString('fr-FR')}.
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-amber-800 bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
              <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
              <span>Format non vérifié sur votre logiciel</span>
            </div>
          )}

          <div className="pt-2">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || isLoading}
              className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
            >
              {isGenerating ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <FileSpreadsheet className="h-4 w-4" />
              )}
              <span>Générer l'export et le pack de preuves</span>
            </button>
          </div>
        </div>
      </div>

      {/* Export Deliverables Card */}
      {exportData && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Livrables prêts au téléchargement</h2>
              <p className="text-xs text-slate-500">
                Fichier d'import comptable certifié et dossier probant horodaté.
              </p>
            </div>
            {isHashMatching ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="h-3.5 w-3.5" />
                Empreinte vérifiée
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                <AlertCircle className="h-3.5 w-3.5" />
                Empreinte divergente
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Accounting File Box */}
            <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">Écritures comptables</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Format {exportData.target} ({exportData.encoding})
                  </p>
                </div>
                <FileSpreadsheet className="h-6 w-6 text-indigo-600" />
              </div>

              <div className="text-xs font-mono text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200 space-y-1">
                <p className="text-slate-400 text-[10px]">SHA-256 du fichier :</p>
                <p className="truncate text-slate-900" title={exportData.file_sha256}>
                  {exportData.file_sha256}
                </p>
              </div>

              <button
                type="button"
                onClick={() => onDownloadFile(exportData.id)}
                className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
              >
                <Download className="h-4 w-4" />
                <span>Télécharger les écritures</span>
              </button>
            </div>

            {/* Evidence Pack Box */}
            <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">Pack de preuves (ZIP)</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Manifeste JSON + Synthèse PDF + Pièces d'origine
                  </p>
                </div>
                <FileArchive className="h-6 w-6 text-purple-600" />
              </div>

              <div className="text-xs font-mono text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200 space-y-1">
                <p className="text-slate-400 text-[10px]">SHA-256 de l'archive :</p>
                <p className="truncate text-slate-900" title={exportData.evidence_pack_sha256}>
                  {exportData.evidence_pack_sha256}
                </p>
              </div>

              <button
                type="button"
                onClick={() => onDownloadEvidencePack(exportData.id)}
                className="w-full py-2.5 px-4 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium text-sm transition-colors flex items-center justify-center gap-2 shadow-sm"
              >
                <Download className="h-4 w-4" />
                <span>Télécharger le pack de preuves</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
