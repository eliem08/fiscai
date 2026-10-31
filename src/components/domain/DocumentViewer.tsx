import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Check, AlertCircle, FileText } from 'lucide-react';

export interface FieldExtraction {
  value: string | number | null;
  confidence: number;
  page: number;
  bbox: [number, number, number, number] | null; // [x0, y0, x1, y1] normalized to 0.0 - 1.0
  confirmed?: boolean;
}

export interface DocumentViewerProps {
  documentId: string;
  filename: string;
  docType: string;
  pageCount: number;
  pages: { pageNumber: number; imageUrl?: string; width: number; height: number }[];
  initialFields: Record<string, FieldExtraction>;
  onSave?: (updatedFields: Record<string, FieldExtraction>) => Promise<void>;
  readOnly?: boolean;
}

export const FIELD_LABELS: Record<string, string> = {
  invoice_number: 'Numéro de facture',
  invoice_date: 'Date de la pièce',
  supplier_name: 'Nom du fournisseur',
  supplier_ice: 'ICE Fournisseur (15 chiffres)',
  supplier_if: 'Identifiant fiscal (IF)',
  client_name: 'Nom du client',
  total_ht: 'Total Hors Taxe (MAD)',
  total_vat: 'Total TVA (MAD)',
  total_ttc: 'Total TTC (MAD)',
  payment_method: 'Mode de règlement',
};

export function DocumentViewer({
  documentId: _documentId,
  filename,
  docType,
  pageCount,
  pages,
  initialFields,
  onSave,
  readOnly = false,
}: DocumentViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoomLevel, setZoomLevel] = useState(100);
  const [focusedField, setFocusedField] = useState<string | null>('supplier_ice');
  const [fields, setFields] = useState<Record<string, FieldExtraction>>(initialFields);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setFields(initialFields);
  }, [initialFields]);

  const activePage = pages.find((p) => p.pageNumber === currentPage) || pages[0] || {
    pageNumber: 1,
    width: 800,
    height: 1131,
  };

  const currentBbox = focusedField && fields[focusedField]?.page === currentPage
    ? fields[focusedField].bbox
    : null;

  const handleZoomIn = () => setZoomLevel((prev) => Math.min(200, prev + 25));
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(50, prev - 25));
  const handleZoomReset = () => setZoomLevel(100);

  const handlePrevPage = () => setCurrentPage((prev) => Math.max(1, prev - 1));
  const handleNextPage = () => setCurrentPage((prev) => Math.min(pageCount, prev + 1));

  const handleFieldChange = (fieldName: string, rawVal: string) => {
    setFields((prev) => {
      const existing = prev[fieldName] || {
        value: null,
        confidence: 1.0,
        page: currentPage,
        bbox: null,
        confirmed: true,
      };
      return {
        ...prev,
        [fieldName]: {
          ...existing,
          value: rawVal,
          confirmed: true,
        },
      };
    });
  };

  const handleFieldKeyDown = (e: React.KeyboardEvent, fieldName: string) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      // Confirm field
      setFields((prev) => ({
        ...prev,
        [fieldName]: {
          ...prev[fieldName],
          confirmed: true,
        },
      }));
      // Advance to next unconfirmed field
      const fieldKeys = Object.keys(FIELD_LABELS);
      const currentIndex = fieldKeys.indexOf(fieldName);
      const nextKey = fieldKeys.slice(currentIndex + 1).find((k) => !fields[k]?.confirmed);
      if (nextKey) {
        setFocusedField(nextKey);
      }
    }
  };

  const handleConfirmField = (fieldName: string) => {
    setFields((prev) => ({
      ...prev,
      [fieldName]: {
        ...prev[fieldName],
        confirmed: true,
      },
    }));
  };

  const handleSaveChanges = async () => {
    setSaveStatus('saving');
    setErrorMessage(null);
    try {
      if (onSave) {
        await onSave(fields);
      }
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Erreur lors de l’enregistrement de la correction');
      setSaveStatus('idle');
    }
  };

  return (
    <div className="flex flex-col h-full bg-paper text-ink font-sans">
      {/* Top Bar per Part E */}
      <header className="flex items-center justify-between border-b border-line px-4 py-2 bg-surface">
        <div className="flex items-center space-x-3">
          <FileText className="w-4 h-4 text-ink-2" />
          <span className="font-heading font-medium text-sm text-ink">{filename}</span>
          <span className="text-xs px-2 py-0.5 rounded border border-line text-ink-2 bg-paper">
            {docType}
          </span>
        </div>

        {/* Viewer Controls: Navigation & Zoom */}
        <div className="flex items-center space-x-4 text-sm">
          {/* Page Navigation: ◀ page X/Y ▶ */}
          <div className="flex items-center space-x-1 border border-line rounded bg-paper px-1">
            <button
              type="button"
              data-testid="page-prev"
              onClick={handlePrevPage}
              disabled={currentPage <= 1}
              className="p-1 text-ink-2 hover:text-ink disabled:opacity-30"
              aria-label="Page précédente"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span data-testid="page-indicator" className="px-2 text-xs font-medium text-ink select-none">
              ◀ page {currentPage}/{pageCount} ▶
            </span>
            <button
              type="button"
              data-testid="page-next"
              onClick={handleNextPage}
              disabled={currentPage >= pageCount}
              className="p-1 text-ink-2 hover:text-ink disabled:opacity-30"
              aria-label="Page suivante"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center space-x-1 border border-line rounded bg-paper px-1">
            <button
              type="button"
              data-testid="zoom-out"
              onClick={handleZoomOut}
              className="p-1 text-ink-2 hover:text-ink"
              aria-label="Zoom arrière"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              data-testid="zoom-reset"
              onClick={handleZoomReset}
              className="px-1.5 text-xs font-mono text-ink-2 hover:text-ink select-none"
              title="Réinitialiser le zoom"
            >
              {zoomLevel}%
            </button>
            <button
              type="button"
              data-testid="zoom-in"
              onClick={handleZoomIn}
              className="p-1 text-ink-2 hover:text-ink"
              aria-label="Zoom avant"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Split View: Left DocumentViewer / Right Proposal Form */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Pane: Document Page Canvas with Bbox Overlay */}
        <div
          data-testid="document-viewport"
          className="flex-1 overflow-auto bg-surface p-6 flex justify-center items-start border-r border-line"
        >
          <div
            className="relative bg-paper shadow-sm border border-line transition-transform origin-top"
            style={{
              width: `${(activePage.width * zoomLevel) / 100}px`,
              height: `${(activePage.height * zoomLevel) / 100}px`,
            }}
          >
            {/* Page raster or SVG layout representation */}
            {activePage.imageUrl ? (
              <img
                src={activePage.imageUrl}
                alt={`Page ${currentPage}`}
                className="w-full h-full object-contain pointer-events-none select-none"
              />
            ) : (
              <div
                data-testid="document-canvas"
                className="w-full h-full p-8 text-xs font-mono text-ink bg-paper select-none flex flex-col justify-between"
              >
                <div>
                  <div className="text-base font-bold font-sans text-ink mb-1">
                    {String(fields.supplier_name?.value || 'Société Atlas SARL')}
                  </div>
                  <div className="text-xs text-ink-2 mb-4">
                    ICE: {String(fields.supplier_ice?.value || '001234567890123')} | IF: {String(fields.supplier_if?.value || '12345678')}
                  </div>
                  <hr className="border-line my-3" />
                  <div className="flex justify-between font-bold text-sm mb-4">
                    <span>FACTURE N°: {String(fields.invoice_number?.value || 'FAC-2026-001')}</span>
                    <span>Date: {String(fields.invoice_date?.value || '2026-03-15')}</span>
                  </div>
                  <div className="text-xs text-ink-2 mb-6">
                    Client: {String(fields.client_name?.value || 'Société Marocaine de Commerce')}
                  </div>
                  <div className="border border-line rounded p-4 mb-6 bg-surface">
                    <div className="flex justify-between font-medium">
                      <span>Prestation de services professionnels et fournitures</span>
                      <span>{String(fields.total_ht?.value || '1000.00')} MAD</span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-line pt-4 flex flex-col items-end space-y-1 text-right">
                  <div className="flex justify-between w-48 text-xs">
                    <span className="text-ink-2">Total HT:</span>
                    <span className="font-medium">{String(fields.total_ht?.value || '1000.00')} MAD</span>
                  </div>
                  <div className="flex justify-between w-48 text-xs">
                    <span className="text-ink-2">Total TVA (20%):</span>
                    <span className="font-medium">{String(fields.total_vat?.value || '200.00')} MAD</span>
                  </div>
                  <div className="flex justify-between w-48 text-sm font-bold border-t border-line pt-1 text-ink">
                    <span>Total TTC:</span>
                    <span>{String(fields.total_ttc?.value || '1200.00')} MAD</span>
                  </div>
                </div>
              </div>
            )}

            {/* Bbox Highlight Overlay on Field Focus (160ms ease-out, respecting prefers-reduced-motion) */}
            {currentBbox && (
              <div
                data-testid="bbox-overlay"
                className="absolute pointer-events-none z-20 border-2 border-sky bg-[#E3F3F9]/40 motion-reduce:transition-none"
                style={{
                  left: `${currentBbox[0] * 100}%`,
                  top: `${currentBbox[1] * 100}%`,
                  width: `${(currentBbox[2] - currentBbox[0]) * 100}%`,
                  height: `${(currentBbox[3] - currentBbox[1]) * 100}%`,
                  transition: 'all 160ms cubic-bezier(0, 0, 0.2, 1)',
                }}
              >
                <span
                  data-testid="bbox-label"
                  className="absolute -top-5 left-0 bg-sky text-ink text-[10px] font-semibold px-1.5 py-0.5 rounded-sm whitespace-nowrap"
                >
                  {FIELD_LABELS[focusedField!] || focusedField}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Field Extraction & Correction Flow */}
        <aside className="w-96 overflow-y-auto bg-paper p-5 flex flex-col justify-between border-l border-line">
          <div>
            <div className="mb-4">
              <h2 className="text-base font-heading font-semibold text-ink">Champs extraits</h2>
              <p className="text-xs text-ink-2 mt-0.5">
                Sélectionnez un champ pour afficher son repère source sur la pièce.
              </p>
            </div>

            {/* Fields Form */}
            <div className="space-y-3.5">
              {Object.entries(FIELD_LABELS).map(([key, label]) => {
                const field = fields[key] || {
                  value: '',
                  confidence: 0,
                  page: 1,
                  bbox: null,
                  confirmed: false,
                };
                const isFocused = focusedField === key;
                const isConfirmed = !!field.confirmed;

                return (
                  <div
                    key={key}
                    data-testid={`field-container-${key}`}
                    className={`p-2.5 rounded border transition-colors ${
                      isFocused ? 'border-sky bg-sky-wash/30' : 'border-line bg-paper'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <label htmlFor={`input-${key}`} className="text-xs font-medium text-ink flex items-center gap-1.5">
                        {label}
                      </label>

                      {/* Unconfirmed / Confirmed indicator per Part E */}
                      {isConfirmed ? (
                        <span className="flex items-center gap-1 text-[11px] text-ok font-medium">
                          <Check className="w-3 h-3" />
                          Confirmé
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleConfirmField(key)}
                          className="flex items-center gap-1 text-[11px] text-pink-ink font-medium hover:underline"
                          title="Cliquer ou appuyer sur Entrée pour confirmer"
                        >
                          {/* 8px pink dot per Part E */}
                          <span
                            data-testid="unconfirmed-marker"
                            className="w-2 h-2 rounded-full bg-pink inline-block"
                          />
                          à confirmer
                        </button>
                      )}
                    </div>

                    <input
                      id={`input-${key}`}
                      data-testid={`field-input-${key}`}
                      type="text"
                      readOnly={readOnly}
                      value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                      onFocus={() => {
                        setFocusedField(key);
                        if (field.page && field.page !== currentPage) {
                          setCurrentPage(field.page);
                        }
                      }}
                      onChange={(e) => handleFieldChange(key, e.target.value)}
                      onKeyDown={(e) => handleFieldKeyDown(e, key)}
                      className="w-full text-xs px-2.5 py-1.5 rounded border border-line bg-paper text-ink focus:outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Action Footer & Audit Notification */}
          <div className="mt-6 pt-4 border-t border-line space-y-3">
            {errorMessage && (
              <div className="text-xs text-fail flex items-start gap-1.5 p-2 bg-fail/5 border border-fail/20 rounded">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            )}

            {saveStatus === 'saved' && (
              <div
                data-testid="save-success-banner"
                className="text-xs text-ok flex items-center gap-1.5 p-2 bg-ok/5 border border-ok/20 rounded font-medium"
              >
                <Check className="w-4 h-4" />
                <span>Correction enregistrée et rattachée au dossier d’audit.</span>
              </div>
            )}

            <button
              type="button"
              data-testid="save-corrections-btn"
              disabled={readOnly || saveStatus === 'saving'}
              onClick={handleSaveChanges}
              className="w-full py-2 px-4 rounded font-heading font-medium text-xs bg-sky text-ink hover:bg-sky/90 transition-colors disabled:opacity-50"
            >
              {saveStatus === 'saving' ? 'Enregistrement…' : 'Enregistrer les modifications'}
            </button>

            <p className="text-[11px] text-ink-2 leading-relaxed">
              Toute modification manuelle génère un enregistrement d’audit immuable conformément à la règle A.5.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
