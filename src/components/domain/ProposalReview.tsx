import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  HelpCircle,
  Check,
  Tag,
} from 'lucide-react';

export interface ProposalLine {
  id: string;
  line_no: number;
  account_id: string;
  account_code: string;
  counterparty_id?: string | null;
  label: string;
  currency: string;
  debit_tx?: number;
  credit_tx?: number;
  debit_mad: number;
  credit_mad: number;
  tax_code?: string | null;
  due_date?: string | null;
  evidence_refs: Array<{
    field?: string;
    bbox?: [number, number, number, number]; // [x0, y0, x1, y1] normalized 0-1
    page?: number;
    rule_ref?: string;
    value?: unknown;
    document_version_id?: string;
    document_id?: string;
  }>;
}

export interface Proposal {
  id: string;
  work_request_id: string;
  revision: number;
  journal_code: string;
  entry_date: string;
  label: string;
  status: 'proposed' | 'edited' | 'approved' | 'exported' | 'superseded' | 'rejected';
  rule_refs: string[];
  lines: ProposalLine[];
}

export interface ProposalReviewProps {
  proposals: Proposal[];
  initialActiveId?: string;
  onUpdateLines?: (proposalId: string, lines: ProposalLine[]) => Promise<void>;
  documentPageUrl?: string;
  documentPageCount?: number;
  readOnly?: boolean;
}

export function ProposalReview({
  proposals,
  initialActiveId,
  onUpdateLines,
  documentPageUrl,
  documentPageCount = 1,
  readOnly = false,
}: ProposalReviewProps) {
  const [activeId, setActiveId] = useState<string>(
    initialActiveId || proposals[0]?.id || ''
  );
  const [focusedLineNo, setFocusedLineNo] = useState<number | null>(1);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editingLines, setEditingLines] = useState<ProposalLine[]>([]);
  const [confirmedLines, setConfirmedLines] = useState<Set<number>>(new Set());
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const activeProposal = useMemo(
    () => proposals.find((p) => p.id === activeId) || proposals[0],
    [proposals, activeId]
  );

  useEffect(() => {
    if (activeProposal) {
      setEditingLines(activeProposal.lines);
      setFocusedLineNo(activeProposal.lines[0]?.line_no || 1);
      setConfirmedLines(new Set());
    }
  }, [activeProposal]);

  const activeIndex = proposals.findIndex((p) => p.id === activeId);

  // Compute balance
  const currentLines = useMemo(
    () => (isEditing ? editingLines : activeProposal?.lines || []),
    [isEditing, editingLines, activeProposal]
  );
  const totalDebit = useMemo(
    () => currentLines.reduce((acc, l) => acc + (Number(l.debit_mad) || 0), 0),
    [currentLines]
  );
  const totalCredit = useMemo(
    () => currentLines.reduce((acc, l) => acc + (Number(l.credit_mad) || 0), 0),
    [currentLines]
  );
  const delta = Math.abs(totalDebit - totalCredit);
  const isBalanced = delta < 0.009;

  // Active evidence bbox
  const focusedLine = currentLines.find((l) => l.line_no === focusedLineNo);
  const activeBbox = focusedLine?.evidence_refs?.[0]?.bbox || null;
  const activeBboxPage = focusedLine?.evidence_refs?.[0]?.page || 1;

  useEffect(() => {
    if (activeBboxPage) {
      setCurrentPage(activeBboxPage);
    }
  }, [activeBboxPage]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  const handleSaveEdits = async () => {
    if (onUpdateLines && activeProposal) {
      await onUpdateLines(activeProposal.id, editingLines);
    }
    setIsEditing(false);
    showToast("Modifications enregistrées");
  };

  const handleNextProposal = useCallback(() => {
    if (activeIndex < proposals.length - 1) {
      setActiveId(proposals[activeIndex + 1].id);
      setIsEditing(false);
    }
  }, [activeIndex, proposals]);

  const handlePrevProposal = useCallback(() => {
    if (activeIndex > 0) {
      setActiveId(proposals[activeIndex - 1].id);
      setIsEditing(false);
    }
  }, [activeIndex, proposals]);

  // Keyboard navigation per ARCHITECTURE.md Part E & Phase 3 Item 5:
  // Enter confirms the focused line or field only. Approval exists only at monthly-file level (Phase 5).
  // No keyboard path triggers approval.
  const handleConfirmLine = useCallback((lineNo: number | null) => {
    if (!lineNo) return;
    setConfirmedLines((prev) => new Set(prev).add(lineNo));
    showToast("Ligne confirmée");
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is inside an input/textarea
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown') {
        e.preventDefault();
        handleNextProposal();
      } else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp') {
        e.preventDefault();
        handlePrevProposal();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        handleConfirmLine(focusedLineNo);
      } else if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        if (!readOnly && activeProposal?.status !== 'approved') {
          setIsEditing((prev) => !prev);
        }
      } else if (e.key === '?') {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNextProposal, handlePrevProposal, handleConfirmLine, focusedLineNo, readOnly, activeProposal]);

  if (!activeProposal) {
    return (
      <div className="p-8 text-center text-ink-2 font-sans" data-testid="proposal-empty">
        Aucune proposition d'écriture à afficher.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-paper text-ink font-sans">
      {/* Top Header / Bar */}
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5 bg-surface">
        <div className="flex items-center space-x-3">
          <FileText className="w-4 h-4 text-ink-2" />
          <span className="font-heading font-medium text-sm text-ink">{activeProposal.label}</span>
          <span className="text-xs px-2 py-0.5 rounded border border-line bg-paper text-ink font-mono font-medium">
            {activeProposal.journal_code}
          </span>
          <span className="text-xs text-ink-2">
            Révision {activeProposal.revision}
          </span>
          <span
            data-testid="proposal-status-badge"
            className="text-xs px-2 py-0.5 rounded font-medium bg-paper text-ink-2 border border-line"
          >
            {activeProposal.revision > 1 ? 'Modifiée' : 'Proposée'}
          </span>
        </div>

        {/* Action Controls & Navigation */}
        <div className="flex items-center space-x-3">
          {/* Navigation J/K */}
          <div className="flex items-center space-x-1 border border-line rounded bg-paper px-1">
            <button
              type="button"
              data-testid="prev-proposal-btn"
              onClick={handlePrevProposal}
              disabled={activeIndex <= 0}
              className="p-1 text-ink-2 hover:text-ink disabled:opacity-30"
              title="Écriture précédente (K)"
              aria-label="Écriture précédente (K)"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 text-xs font-mono text-ink select-none">
              {activeIndex + 1}/{proposals.length}
            </span>
            <button
              type="button"
              data-testid="next-proposal-btn"
              onClick={handleNextProposal}
              disabled={activeIndex >= proposals.length - 1}
              className="p-1 text-ink-2 hover:text-ink disabled:opacity-30"
              title="Écriture suivante (J)"
              aria-label="Écriture suivante (J)"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowShortcuts((prev) => !prev)}
            className="p-1.5 text-ink-2 hover:text-ink rounded border border-line bg-paper"
            title="Raccourcis clavier (?)"
            aria-label="Raccourcis clavier"
          >
            <HelpCircle className="w-4 h-4" />
          </button>

          {!readOnly && isEditing && (
            <button
              type="button"
              data-testid="save-edits-btn"
              onClick={handleSaveEdits}
              className="px-3 py-1 bg-emerald-600 text-white rounded text-xs font-medium hover:bg-emerald-700 transition-colors"
            >
              Enregistrer
            </button>
          )}

          {!readOnly && (
            <button
              type="button"
              data-testid="confirm-line-btn"
              onClick={() => handleConfirmLine(focusedLineNo)}
              className="px-3 py-1 bg-ink text-paper rounded text-xs font-medium hover:bg-black transition-colors flex items-center space-x-1"
            >
              <Check className="w-3.5 h-3.5 mr-1" />
              <span>Confirmer la ligne</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Split Pane Layout per Part E */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Document Viewer with Bbox Overlay */}
        <div className="w-1/2 border-r border-line flex flex-col bg-slate-50 relative">
          {/* Viewer toolbar */}
          <div className="flex items-center justify-between border-b border-line px-3 py-1.5 bg-surface text-xs text-ink-2">
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="p-1 hover:text-ink disabled:opacity-30"
                title="Page précédente"
                aria-label="Page précédente"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span>Source : page {currentPage}/{documentPageCount}</span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(documentPageCount, p + 1))}
                disabled={currentPage >= documentPageCount}
                className="p-1 hover:text-ink disabled:opacity-30"
                title="Page suivante"
                aria-label="Page suivante"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.max(50, z - 25))}
                className="p-1 hover:text-ink"
                title="Zoom arrière"
                aria-label="Zoom arrière"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-xs">{zoomLevel}%</span>
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.min(200, z + 25))}
                className="p-1 hover:text-ink"
                title="Zoom avant"
                aria-label="Zoom avant"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Page Canvas Container */}
          <div className="flex-1 overflow-auto p-4 flex items-center justify-center relative">
            <div
              className="relative shadow bg-white transition-transform duration-100 ease-out origin-center"
              style={{
                width: `${(600 * zoomLevel) / 100}px`,
                height: `${(850 * zoomLevel) / 100}px`,
              }}
            >
              {documentPageUrl ? (
                <img
                  src={documentPageUrl}
                  alt={`Document page ${currentPage}`}
                  className="w-full h-full object-contain pointer-events-none select-none"
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center border-2 border-dashed border-line text-ink-2 text-xs">
                  <FileText className="w-8 h-8 mb-2 opacity-40" />
                  <span>Aperçu de la pièce comptable</span>
                </div>
              )}

              {/* Bounding Box Highlight Overlay */}
              {activeBbox && activeBboxPage === currentPage && (
                <div
                  data-testid="evidence-bbox-overlay"
                  className="absolute pointer-events-none transition-all duration-160 ease-out border-2 border-sky bg-sky-wash/40 rounded-sm"
                  style={{
                    left: `${activeBbox[0] * 100}%`,
                    top: `${activeBbox[1] * 100}%`,
                    width: `${(activeBbox[2] - activeBbox[0]) * 100}%`,
                    height: `${(activeBbox[3] - activeBbox[1]) * 100}%`,
                  }}
                />
              )}
            </div>
          </div>
        </div>

        {/* Right: Accounting Entry Table */}
        <div className="w-1/2 flex flex-col bg-paper overflow-y-auto">
          {/* Proposal Meta & Rule Tags */}
          <div className="p-4 border-b border-line bg-surface/50">
            <div className="flex items-center justify-between text-xs text-ink-2 mb-2">
              <div>
                <span>Date d'écriture : </span>
                <span className="font-mono font-medium text-ink">{activeProposal.entry_date}</span>
              </div>
              <div>
                <span>Pièce source : </span>
                <span className="font-mono">{activeProposal.id.slice(0, 8)}</span>
              </div>
            </div>

            {/* Jurisdiction Rule Badges */}
            {activeProposal.rule_refs && activeProposal.rule_refs.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {activeProposal.rule_refs.map((ref) => (
                  <span
                    key={ref}
                    className="inline-flex items-center text-[10px] px-2 py-0.5 rounded bg-sky-wash text-[#02435c] border border-sky/30 font-mono font-medium"
                  >
                    <Tag className="w-2.5 h-2.5 mr-1" />
                    {ref}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Journal Lines Table */}
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-surface sticky top-0 border-b border-line z-10 text-ink-2 font-medium">
                <tr>
                  <th scope="col" className="py-2 px-3 w-12 text-center">N°</th>
                  <th scope="col" className="py-2 px-3 w-24">Compte</th>
                  <th scope="col" className="py-2 px-3">Libellé</th>
                  <th scope="col" className="py-2 px-3 w-28 text-right">Débit (MAD)</th>
                  <th scope="col" className="py-2 px-3 w-28 text-right">Crédit (MAD)</th>
                  <th scope="col" className="py-2 px-3 w-16 text-center">Preuve</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {currentLines.map((line) => {
                  const isFocused = line.line_no === focusedLineNo;
                  const isConfirmed = confirmedLines.has(line.line_no);
                  const hasEvidence = line.evidence_refs && line.evidence_refs.length > 0;

                  return (
                    <tr
                      key={line.line_no}
                      data-testid={`proposal-line-row-${line.line_no}`}
                      onClick={() => setFocusedLineNo(line.line_no)}
                      className={`cursor-pointer transition-colors duration-100 ${
                        isFocused
                          ? 'bg-sky-wash/50 border-l-2 border-l-sky'
                          : 'hover:bg-slate-50'
                      }`}
                    >
                      <td className="py-2 px-3 text-center font-mono text-ink-2">
                        {line.line_no}
                      </td>
                      <td className="py-2 px-3 font-mono font-medium text-ink">
                        {line.account_code}
                      </td>
                      <td className="py-2 px-3 text-ink">
                        <div className="flex items-center space-x-1.5">
                          <span>{line.label}</span>
                          {line.tax_code && (
                            <span className="text-[10px] px-1 py-0.2 bg-slate-100 text-ink-2 rounded border border-line">
                              {line.tax_code}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right font-mono tabular-nums text-ink">
                        {line.debit_mad > 0
                          ? line.debit_mad.toLocaleString('fr-FR', {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })
                          : '—'}
                      </td>
                      <td className="py-2 px-3 text-right font-mono tabular-nums text-ink">
                        {line.credit_mad > 0
                          ? line.credit_mad.toLocaleString('fr-FR', {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })
                          : '—'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        {hasEvidence ? (
                          <span
                            title="Ligne liée à une région du document"
                            className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-sky-wash text-sky-ink"
                          >
                            <FileText className="w-3 h-3" />
                          </span>
                        ) : (
                          <span className="text-ink-2 opacity-30">—</span>
                        )}
                        {isConfirmed && (
                          <Check className="w-3.5 h-3.5 text-emerald-600 inline ml-1" />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Bottom Balance Strip & Status */}
          <div className="border-t border-line p-3 bg-surface flex items-center justify-between text-xs">
            <div className="flex items-center space-x-4 font-mono">
              <div>
                <span className="text-ink-2">Total Débit : </span>
                <span className="font-medium text-ink">
                  {totalDebit.toLocaleString('fr-FR', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}{' '}
                  MAD
                </span>
              </div>
              <div>
                <span className="text-ink-2">Total Crédit : </span>
                <span className="font-medium text-ink">
                  {totalCredit.toLocaleString('fr-FR', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}{' '}
                  MAD
                </span>
              </div>
            </div>

            {/* Dynamic Balance Badge */}
            <div
              data-testid="balance-indicator"
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded font-medium ${
                isBalanced
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border border-rose-200'
              }`}
            >
              {isBalanced ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Équilibré (Δ = 0,00 MAD)</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                  <span>
                    Déséquilibré (Δ ={' '}
                    {delta.toLocaleString('fr-FR', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    MAD)
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Toast */}
      {toastMessage && (
        <div
          data-testid="toast-message"
          className="fixed bottom-4 right-4 bg-ink text-paper px-4 py-2 rounded shadow text-xs font-medium"
        >
          {toastMessage}
        </div>
      )}

      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg border border-line p-5 max-w-sm w-full text-xs shadow-lg">
            <h3 className="font-heading font-medium text-sm text-ink mb-3">Raccourcis clavier</h3>
            <ul className="space-y-2 text-ink-2">
              <li className="flex justify-between">
                <span>Proposition suivante</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">J / ↓</kbd>
              </li>
              <li className="flex justify-between">
                <span>Proposition précédente</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">K / ↑</kbd>
              </li>
              <li className="flex justify-between">
                <span>Confirmer la ligne</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">Entrée</kbd>
              </li>
              <li className="flex justify-between">
                <span>Éditer l'écriture</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">E</kbd>
              </li>
              <li className="flex justify-between">
                <span>Aide raccourcis</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">?</kbd>
              </li>
            </ul>
            <div className="mt-4 pt-3 border-t border-line text-right">
              <button
                type="button"
                onClick={() => setShowShortcuts(false)}
                className="px-3 py-1 bg-paper border border-line rounded text-ink hover:bg-slate-100"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
