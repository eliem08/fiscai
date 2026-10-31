import React, { useEffect, useState, useMemo } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  HelpCircle,
  Edit2,
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
    value?: any;
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
  onApprove?: (proposalId: string) => Promise<void>;
  onUpdateLines?: (proposalId: string, lines: ProposalLine[]) => Promise<void>;
  documentPageUrl?: string;
  documentPageCount?: number;
  readOnly?: boolean;
}

export function ProposalReview({
  proposals,
  initialActiveId,
  onApprove,
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
    }
  }, [activeProposal]);

  const activeIndex = proposals.findIndex((p) => p.id === activeId);

  // Compute balance
  const currentLines = isEditing ? editingLines : activeProposal?.lines || [];
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

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  const handleNextProposal = () => {
    if (activeIndex < proposals.length - 1) {
      setActiveId(proposals[activeIndex + 1].id);
      setIsEditing(false);
    }
  };

  const handlePrevProposal = () => {
    if (activeIndex > 0) {
      setActiveId(proposals[activeIndex - 1].id);
      setIsEditing(false);
    }
  };

  const handleApprove = async () => {
    if (!activeProposal || readOnly || activeProposal.status === 'approved') return;
    if (!isBalanced) {
      showToast("L'écriture doit être équilibrée avant validation.");
      return;
    }
    if (onApprove) {
      await onApprove(activeProposal.id);
      showToast("Écriture validée");
    }
  };

  // Keyboard navigation per ARCHITECTURE.md Part E:
  // J/K next/prev entry, E edit, Enter approve/confirm, ? shortcuts
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
        handleApprove();
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
  }, [activeIndex, proposals, activeProposal, isBalanced, readOnly]);

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
            className={`text-xs px-2 py-0.5 rounded font-medium ${
              activeProposal.status === 'approved'
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-paper text-ink-2 border border-line'
            }`}
          >
            {activeProposal.status === 'approved' ? 'Validée' : 'Proposée'}
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
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowShortcuts((prev) => !prev)}
            className="p-1.5 text-ink-2 hover:text-ink rounded border border-line bg-paper"
            title="Raccourcis clavier (?)"
          >
            <HelpCircle className="w-4 h-4" />
          </button>

          {!readOnly && activeProposal.status !== 'approved' && (
            <button
              type="button"
              data-testid="approve-proposal-btn"
              onClick={handleApprove}
              disabled={!isBalanced}
              className="px-3 py-1 bg-ink text-paper rounded text-xs font-medium hover:bg-black transition-colors disabled:opacity-40 flex items-center space-x-1"
            >
              <Check className="w-3.5 h-3.5 mr-1" />
              <span>Valider l'écriture</span>
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
              <span>Source : page {currentPage}/{documentPageCount}</span>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.max(50, z - 25))}
                className="p-1 hover:text-ink"
                title="Zoom arrière"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-xs">{zoomLevel}%</span>
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.min(200, z + 25))}
                className="p-1 hover:text-ink"
                title="Zoom avant"
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
                  alt="Pièce justificative"
                  className="w-full h-full object-contain pointer-events-none select-none"
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center p-6 text-slate-400 border border-dashed border-slate-300">
                  <FileText className="w-12 h-12 mb-2 text-slate-300" />
                  <span className="text-xs">Aperçu de la pièce comptable</span>
                </div>
              )}

              {/* Bbox Highlight Overlay per Part E: 2px --sky box with --sky-wash fill */}
              {activeBbox && activeBboxPage === currentPage && (
                <div
                  data-testid="evidence-bbox"
                  className="absolute pointer-events-none border-2 border-sky-500 bg-sky-500/15 rounded-sm transition-all duration-160 ease-out motion-reduce:transition-none"
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

        {/* Right: Accounting Lines Table & Balance */}
        <div className="w-1/2 flex flex-col bg-surface overflow-hidden">
          {/* Header & Balance Badge */}
          <div className="border-b border-line p-4 flex items-center justify-between bg-surface">
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-heading font-medium text-base text-ink">
                  {activeProposal.journal_code} · {activeProposal.entry_date}
                </span>
                <span className="text-xs text-ink-2">
                  Facture {activeProposal.label}
                </span>
              </div>
            </div>

            {/* Balance Badge per Part E */}
            <div
              data-testid="balance-indicator"
              className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-medium ${
                isBalanced
                  ? 'bg-sky-50 text-sky-800 border border-sky-200'
                  : 'bg-rose-50 text-rose-800 border border-rose-200'
              }`}
            >
              {isBalanced ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-sky-600" />
                  <span>Équilibrée ✓ (Δ = 0,00 MAD)</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <span>Déséquilibrée (Δ = {delta.toFixed(2)} MAD)</span>
                </>
              )}
            </div>
          </div>

          {/* Lines Table */}
          <div className="flex-1 overflow-auto p-4">
            <table className="w-full text-left text-xs border border-line rounded overflow-hidden">
              <thead className="bg-paper border-b border-line text-ink-2 font-medium">
                <tr>
                  <th className="py-2 px-3 w-20">Compte</th>
                  <th className="py-2 px-3">Libellé</th>
                  <th className="py-2 px-3 text-right w-24">Débit (MAD)</th>
                  <th className="py-2 px-3 text-right w-24">Crédit (MAD)</th>
                  <th className="py-2 px-3 w-16 text-center">TVA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {currentLines.map((line) => {
                  const isFocused = focusedLineNo === line.line_no;
                  return (
                    <tr
                      key={line.id || line.line_no}
                      data-testid={`proposal-line-${line.line_no}`}
                      onClick={() => setFocusedLineNo(line.line_no)}
                      className={`cursor-pointer transition-colors ${
                        isFocused ? 'bg-sky-50/70 font-medium' : 'hover:bg-slate-50'
                      }`}
                    >
                      <td className="py-2 px-3 font-mono font-medium text-ink">
                        {line.account_code}
                      </td>
                      <td className="py-2 px-3 text-ink truncate max-w-[200px]" title={line.label}>
                        {line.label}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink">
                        {line.debit_mad > 0 ? line.debit_mad.toLocaleString('fr-FR', { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-ink">
                        {line.credit_mad > 0 ? line.credit_mad.toLocaleString('fr-FR', { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        {line.tax_code ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border border-line bg-paper text-ink-2 font-mono">
                            {line.tax_code.replace('STANDARD_', '').replace('REDUCED_', '')}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t border-line bg-paper font-medium text-xs">
                <tr>
                  <td colSpan={2} className="py-2 px-3 text-ink-2 font-heading">
                    Totaux
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-ink font-semibold">
                    {totalDebit.toLocaleString('fr-FR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-ink font-semibold">
                    {totalCredit.toLocaleString('fr-FR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2 px-3"></td>
                </tr>
              </tfoot>
            </table>

            {/* Evidence summary box */}
            {focusedLine && (
              <div className="mt-4 p-3 bg-paper border border-line rounded text-xs text-ink-2">
                <div className="font-heading font-medium text-ink mb-1 flex items-center space-x-1">
                  <Tag className="w-3.5 h-3.5 text-sky-600 mr-1" />
                  <span>Traçabilité & Source de la ligne #{focusedLine.line_no}</span>
                </div>
                {focusedLine.evidence_refs?.length > 0 ? (
                  <ul className="space-y-1 mt-1 text-[11px]">
                    {focusedLine.evidence_refs.map((ev, i) => (
                      <li key={i} className="flex items-center space-x-2">
                        <span className="font-mono text-ink">[{ev.field || 'montant'}]</span>
                        <span>Source page {ev.page || 1}</span>
                        {ev.rule_ref && (
                          <span className="text-slate-400">· Règle : {ev.rule_ref}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-slate-400 text-[11px]">Aucun repère extrait pour cette ligne.</span>
                )}
              </div>
            )}
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
                <span>Valider l'écriture</span>
                <kbd className="font-mono bg-paper border border-line px-1.5 py-0.5 rounded">Entrée</kbd>
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
