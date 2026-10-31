import { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import type { DocumentType } from '@/types/models';
import { useTranslation } from '@/i18n';
import { validateUploadFile, ALLOWED_FILE_EXTENSIONS } from '@/lib/validation';

const DOC_TYPES: DocumentType[] = [
  'commercial_invoice',
  'packing_list',
  'transport_document',
  'certificate_origin',
  'customs_declaration',
  'vat_declaration',
  'other',
];

interface UploadZoneProps {
  onUpload: (file: File, documentType: DocumentType) => Promise<void>;
  disabled?: boolean;
}

export function UploadZone({ onUpload, disabled }: UploadZoneProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [documentType, setDocumentType] = useState<DocumentType>('commercial_invoice');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFiles(files: FileList | null) {
    setError(null);
    const file = files?.[0];
    if (!file) return;
    const check = validateUploadFile({ name: file.name, size: file.size, type: file.type });
    if (!check.valid) {
      setError(check.reason ?? 'Fichier invalide.');
      return;
    }
    setBusy(true);
    try {
      await onUpload(file, documentType);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec de l’envoi du document.');
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  return (
    <div className="card p-5" data-testid="upload-zone">
      <label className="label" htmlFor="upload-doc-type">
        {t('upload.docType')}
      </label>
      <select
        id="upload-doc-type"
        className="input mb-3"
        value={documentType}
        onChange={(e) => setDocumentType(e.target.value as DocumentType)}
        disabled={disabled || busy}
      >
        {DOC_TYPES.map((value) => (
          <option key={value} value={value}>
            {t(`docType.${value}`)}
          </option>
        ))}
      </select>

      <div
        className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          disabled ? 'border-slate-200 bg-slate-50' : 'border-brand-200 bg-brand-50/40'
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!disabled && !busy) void handleFiles(e.dataTransfer.files);
        }}
      >
        <UploadCloud className="mb-2 h-8 w-8 text-brand-500" aria-hidden="true" />
        <p className="text-sm text-slate-600">{t('upload.dropHint')}</p>
        <button
          type="button"
          className="btn-primary mt-2"
          disabled={disabled || busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? t('upload.sending') : t('upload.choose')}
        </button>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          aria-label={t('upload.selectAria')}
          accept={ALLOWED_FILE_EXTENSIONS.map((e) => '.' + e).join(',')}
          onChange={(e) => void handleFiles(e.target.files)}
          disabled={disabled || busy}
        />
        <p className="mt-2 text-xs text-slate-400">{t('upload.formats')}</p>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm font-medium text-red-700" data-testid="upload-error">
          {error}
        </p>
      )}
    </div>
  );
}
