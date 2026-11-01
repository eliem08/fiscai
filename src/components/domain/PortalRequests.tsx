import { useState } from 'react';
import {
  MessageSquare,
  Send,
  CheckCircle2,
  Clock,
} from 'lucide-react';

export interface PortalRequestItem {
  id: string;
  client_entity_id: string;
  legal_name: string;
  work_request_id?: string | null;
  document_id?: string | null;
  code: string;
  message: string;
  prompt: string;
  created_at: string;
}

export interface PortalRequestsProps {
  requests: PortalRequestItem[];
  onAnswerRequest: (
    requestId: string,
    response: string,
    attachedDocumentId?: string,
  ) => Promise<void>;
  isLoading?: boolean;
}

export function PortalRequests({
  requests,
  onAnswerRequest,
  isLoading: _isLoading = false,
}: PortalRequestsProps) {
  const [activeRequest, setActiveRequest] = useState<PortalRequestItem | null>(null);
  const [responseText, setResponseText] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleOpenAnswerModal = (req: PortalRequestItem) => {
    setActiveRequest(req);
    setResponseText('');
  };

  const handleSubmitAnswer = async () => {
    if (!activeRequest || !responseText.trim()) return;
    setIsSubmitting(true);
    try {
      await onAnswerRequest(activeRequest.id, responseText.trim());
      setToastMessage('Réponse transmise au cabinet');
      setActiveRequest(null);
      setResponseText('');
    } finally {
      setIsSubmitting(false);
    }
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

      {/* Header */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-600">
            <MessageSquare className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Demandes de précision en attente</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Votre comptable a besoin d'éléments complémentaires pour finaliser votre dossier.
            </p>
          </div>
        </div>
      </div>

      {/* Requests List */}
      {requests.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto" />
          <h2 className="text-base font-bold text-slate-900 mt-4">Aucune demande en attente</h2>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Toutes les demandes de justificatifs et de précisions ont été traitées.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {requests.map((req) => (
            <div
              key={req.id}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4 hover:border-slate-300 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    {req.code}
                  </span>
                  <span className="font-semibold text-sm text-slate-900">{req.legal_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Clock className="h-3.5 w-3.5" />
                  <span>{new Date(req.created_at).toLocaleDateString('fr-FR')}</span>
                </div>
              </div>

              <div>
                <p className="text-xs font-medium text-slate-500">Objet de l'anomalie :</p>
                <p className="text-sm text-slate-800 mt-0.5">{req.message}</p>
              </div>

              <div className="bg-indigo-50/50 p-3.5 rounded-lg border border-indigo-100">
                <p className="text-xs font-semibold text-indigo-950">Message de votre cabinet :</p>
                <p className="text-sm text-indigo-900 mt-1">{req.prompt}</p>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => handleOpenAnswerModal(req)}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs sm:text-sm transition-colors flex items-center gap-1.5 shadow-sm"
                >
                  <Send className="h-3.5 w-3.5" />
                  <span>Répondre à la demande</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Answer Modal */}
      {activeRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Répondre au cabinet comptable</h3>
              <button
                type="button"
                aria-label="Fermer le dialogue de réponse"
                onClick={() => setActiveRequest(null)}
                className="text-slate-400 hover:text-slate-600 text-xl font-bold"
              >
                &times;
              </button>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs space-y-1">
              <p className="text-slate-500 font-medium">Demande : {activeRequest.code}</p>
              <p className="text-slate-800 font-semibold">{activeRequest.prompt}</p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="portal-explanation-input" className="block text-xs font-semibold text-slate-700">Votre explication</label>
              <textarea
                id="portal-explanation-input"
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                placeholder="Indiquez ici vos précisions, la nature de l'opération ou les références demandées..."
                className="w-full h-32 rounded-lg border border-slate-300 p-3 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3">
              <button
                type="button"
                onClick={() => setActiveRequest(null)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 text-sm font-medium"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleSubmitAnswer}
                disabled={!responseText.trim() || isSubmitting}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
              >
                <Send className="h-3.5 w-3.5" />
                <span>Envoyer la réponse</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
