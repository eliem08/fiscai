import React, { useState, useMemo, useCallback } from 'react';
import {
  ArrowRightLeft,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Building2,
  Calendar,
  Layers,
  Filter,
} from 'lucide-react';

export interface BankTransactionLine {
  id: string;
  line_index: number;
  booking_date: string;
  value_date?: string | null;
  amount: number; // Signed: positive = credit, negative = debit
  currency: string;
  description: string;
  external_reference?: string | null;
}

export interface ProposalSummary {
  id: string;
  journal_code: string;
  entry_date: string;
  label: string;
  amount_ttc: number;
  vat_amount?: number;
  counterparty_name?: string;
  invoice_number?: string;
}

export interface ReconciliationMatchItem {
  id: string;
  bank_transaction_id?: string | null;
  journal_proposal_id?: string | null;
  amount_mad: number;
  bank_date?: string | null;
  bank_desc?: string | null;
  proposal_date?: string | null;
  proposal_label?: string | null;
}

export interface ReconciliationMatch {
  id: string;
  status: 'proposed' | 'accepted' | 'rejected' | 'superseded';
  score?: number | null;
  reasons: string[];
  difference_mad: number;
  difference_kind?: 'vat_withheld' | 'bank_fee' | 'fx' | 'rounding' | 'unexplained' | null;
  decided_by?: string | null;
  decided_at?: string | null;
  items: ReconciliationMatchItem[];
}

export interface ReconciliationScreenProps {
  bankTransactions: BankTransactionLine[];
  proposals: ProposalSummary[];
  matches: ReconciliationMatch[];
  onAcceptMatch: (matchId: string) => Promise<void> | void;
  onRejectMatch: (matchId: string) => Promise<void> | void;
  readOnly?: boolean;
}

const DIFFERENCE_KIND_LABELS: Record<string, string> = {
  vat_withheld: 'TVA retenue à la source',
  bank_fee: 'Frais bancaires',
  fx: 'Écart de change',
  rounding: "Écart d'arrondi",
  unexplained: 'Écart non expliqué',
};

export const ReconciliationScreen: React.FC<ReconciliationScreenProps> = ({
  bankTransactions,
  proposals: _proposals,
  matches,
  onAcceptMatch,
  onRejectMatch,
  readOnly = false,
}) => {
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(
    matches.length > 0 ? matches[0].id : null
  );
  const [filterStatus, setFilterStatus] = useState<'all' | 'proposed' | 'accepted'>('all');
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const filteredMatches = useMemo(() => {
    if (filterStatus === 'all') return matches;
    return matches.filter((m) => m.status === filterStatus);
  }, [matches, filterStatus]);

  const activeMatch = useMemo(() => {
    return matches.find((m) => m.id === selectedMatchId) || filteredMatches[0] || null;
  }, [matches, selectedMatchId, filteredMatches]);

  const acceptedBankTxIds = useMemo(() => {
    const ids = new Set<string>();
    matches
      .filter((m) => m.status === 'accepted')
      .forEach((m) => {
        m.items.forEach((it) => {
          if (it.bank_transaction_id) ids.add(it.bank_transaction_id);
        });
      });
    return ids;
  }, [matches]);

  const handleAccept = useCallback(
    async (matchId: string) => {
      if (readOnly || isProcessing) return;
      setIsProcessing(true);
      setErrorMessage(null);
      try {
        await onAcceptMatch(matchId);
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Impossible d'accepter le rapprochement."
        );
      } finally {
        setIsProcessing(false);
      }
    },
    [onAcceptMatch, readOnly, isProcessing]
  );

  const handleReject = useCallback(
    async (matchId: string) => {
      if (readOnly || isProcessing) return;
      setIsProcessing(true);
      setErrorMessage(null);
      try {
        await onRejectMatch(matchId);
      } catch (err: unknown) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : "Impossible de rejeter le rapprochement."
        );
      } finally {
        setIsProcessing(false);
      }
    },
    [onRejectMatch, readOnly, isProcessing]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!activeMatch) return;
      if (e.key === 'Enter') {
        if (activeMatch.status === 'proposed') {
          e.preventDefault();
          handleAccept(activeMatch.id);
        }
      } else if (e.key === 'Escape') {
        if (activeMatch.status === 'proposed') {
          e.preventDefault();
          handleReject(activeMatch.id);
        }
      }
    },
    [activeMatch, handleAccept, handleReject]
  );

  return (
    <div
      className="flex flex-col h-full bg-slate-50 text-slate-900 focus:outline-none"
      onKeyDown={handleKeyDown}
      tabIndex={0}
      data-testid="reconciliation-screen"
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200">
        <div className="flex items-center space-x-3">
          <ArrowRightLeft className="w-5 h-5 text-emerald-600" />
          <h1 className="text-lg font-semibold text-slate-900">
            Rapprochement bancaire
          </h1>
          <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-700">
            {matches.filter((m) => m.status === 'accepted').length} /{' '}
            {matches.length} rapprochés
          </span>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-sm text-slate-600">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={filterStatus}
              onChange={(e) =>
                setFilterStatus(e.target.value as 'all' | 'proposed' | 'accepted')
              }
              className="px-2.5 py-1 text-sm border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
              aria-label="Filtrer les rapprochements par statut"
            >
              <option value="all">Tous les statuts</option>
              <option value="proposed">À rapprocher</option>
              <option value="accepted">Rapprochés</option>
            </select>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="mx-6 mt-4 p-3 rounded-md bg-rose-50 border border-rose-200 flex items-center space-x-2 text-sm text-rose-800"
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main two-column layout */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        {/* Left column: Bank transactions */}
        <div className="col-span-5 border-r border-slate-200 bg-white flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Building2 className="w-4 h-4 text-slate-500" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Lignes du relevé bancaire
              </h2>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              {bankTransactions.length} lignes
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {bankTransactions.map((tx) => {
              const isAccepted = acceptedBankTxIds.has(tx.id);
              const isMatchingActive =
                activeMatch &&
                activeMatch.items.some((it) => it.bank_transaction_id === tx.id);

              return (
                <div
                  key={tx.id}
                  className={`p-3 transition-colors ${
                    isMatchingActive
                      ? 'bg-emerald-50 border-l-4 border-emerald-600'
                      : isAccepted
                      ? 'bg-slate-50/60 opacity-80'
                      : 'hover:bg-slate-50'
                  }`}
                  data-testid={`bank-line-${tx.id}`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-medium text-slate-500 flex items-center space-x-1">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{tx.booking_date}</span>
                        </span>
                        {isAccepted && (
                          <span className="inline-flex items-center text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                            Rapproché
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm font-medium text-slate-800 line-clamp-1">
                        {tx.description}
                      </p>
                      {tx.external_reference && (
                        <p className="text-xs text-slate-600 font-mono mt-0.5">
                          Réf: {tx.external_reference}
                        </p>
                      )}
                    </div>

                    <div className="text-right">
                      <span
                        className={`text-sm font-mono font-semibold ${
                          tx.amount > 0 ? 'text-emerald-800' : 'text-slate-800'
                        }`}
                      >
                        {tx.amount > 0 ? '+' : ''}
                        {tx.amount.toLocaleString('fr-FR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}{' '}
                        MAD
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right column: Reconciliation Candidates & Detail */}
        <div className="col-span-7 flex flex-col bg-slate-50 overflow-hidden">
          <div className="px-6 py-3 bg-white border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-slate-500" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Candidats de rapprochement
              </h2>
            </div>
            <span className="text-xs text-slate-500">
              {filteredMatches.length} propositions
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {filteredMatches.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-sm">
                Aucun rapprochement correspondant à ce filtre.
              </div>
            ) : (
              filteredMatches.map((m) => {
                const isSelected = activeMatch?.id === m.id;
                const bankItems = m.items.filter((it) => it.bank_transaction_id);
                const propItems = m.items.filter((it) => it.journal_proposal_id);
                const hasDiff = m.difference_mad > 0;

                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedMatchId(m.id)}
                    className={`p-5 rounded-lg border bg-white shadow-sm transition-all cursor-pointer ${
                      isSelected
                        ? 'border-emerald-500 ring-2 ring-emerald-500/20'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    data-testid={`match-card-${m.id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        {m.score !== null && m.score !== undefined && (
                          <div
                            className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                              m.score >= 0.97
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            Score: {(m.score * 100).toFixed(0)}%
                          </div>
                        )}
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-medium ${
                            m.status === 'accepted'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : m.status === 'rejected'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {m.status === 'accepted'
                            ? 'Rapproché'
                            : m.status === 'rejected'
                            ? 'Rejeté'
                            : 'À rapprocher'}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        {m.status === 'proposed' && !readOnly && (
                          <>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAccept(m.id);
                              }}
                              disabled={isProcessing}
                              className="px-3 py-1.5 text-xs font-semibold text-white bg-emerald-700 hover:bg-emerald-800 rounded-md transition-colors flex items-center space-x-1 shadow-sm disabled:opacity-50"
                              data-testid={`btn-accept-${m.id}`}
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Rapprocher</span>
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReject(m.id);
                              }}
                              disabled={isProcessing}
                              className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-md transition-colors flex items-center space-x-1 border border-slate-200 disabled:opacity-50"
                              data-testid={`btn-reject-${m.id}`}
                            >
                              <XCircle className="w-3.5 h-3.5" />
                              <span>Rejeter</span>
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Matched pieces comparison */}
                    <div className="mt-4 grid grid-cols-2 gap-4 p-3 bg-slate-50 rounded-md border border-slate-100 text-xs">
                      <div>
                        <span className="font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                          Banque ({bankItems.length})
                        </span>
                        {bankItems.map((bi) => (
                          <div key={bi.id} className="mt-1">
                            <p className="font-medium text-slate-800 line-clamp-1">
                              {bi.bank_desc || 'Mouvement bancaire'}
                            </p>
                            <div className="flex justify-between items-center text-slate-500 font-mono mt-0.5">
                              <span>{bi.bank_date || ''}</span>
                              <span className="font-semibold text-slate-900">
                                {bi.amount_mad.toFixed(2)} MAD
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="border-l border-slate-200 pl-4">
                        <span className="font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                          Pièce comptable ({propItems.length})
                        </span>
                        {propItems.map((pi) => (
                          <div key={pi.id} className="mt-1">
                            <p className="font-medium text-slate-800 line-clamp-1">
                              {pi.proposal_label || 'Facture'}
                            </p>
                            <div className="flex justify-between items-center text-slate-500 font-mono mt-0.5">
                              <span>{pi.proposal_date || ''}</span>
                              <span className="font-semibold text-slate-900">
                                {pi.amount_mad.toFixed(2)} MAD
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Difference section */}
                    {hasDiff && (
                      <div className="mt-3 p-2.5 bg-amber-50 rounded border border-amber-200 flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                          <span className="font-medium text-amber-900">
                            {m.difference_kind
                              ? DIFFERENCE_KIND_LABELS[m.difference_kind] || m.difference_kind
                              : "Écart de règlement"}
                          </span>
                        </div>
                        <span className="font-mono font-semibold text-amber-900">
                          {m.difference_mad.toFixed(2)} MAD
                        </span>
                      </div>
                    )}

                    {/* Reasons */}
                    {m.reasons.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {m.reasons.map((r, idx) => (
                          <span
                            key={idx}
                            className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
