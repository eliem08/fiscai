import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { DocumentViewer, type FieldExtraction } from '@/components/domain/DocumentViewer';

export function DocumentReviewPage() {
  const { id = 'doc-demo-001' } = useParams<{ id: string }>();

  // Mock initial fields with normalized [x0, y0, x1, y1] bounding boxes
  const [fields, setFields] = useState<Record<string, FieldExtraction>>({
    supplier_name: {
      value: 'Société Atlas SARL',
      confidence: 0.98,
      page: 1,
      bbox: [0.05, 0.04, 0.45, 0.08],
      confirmed: true,
    },
    supplier_ice: {
      value: '001234567890123',
      confidence: 0.99,
      page: 1,
      bbox: [0.05, 0.08, 0.35, 0.11],
      confirmed: false, // à confirmer
    },
    supplier_if: {
      value: '12345678',
      confidence: 0.97,
      page: 1,
      bbox: [0.37, 0.08, 0.55, 0.11],
      confirmed: true,
    },
    invoice_number: {
      value: 'FAC-2026-001',
      confidence: 0.99,
      page: 1,
      bbox: [0.05, 0.14, 0.38, 0.18],
      confirmed: false, // à confirmer
    },
    invoice_date: {
      value: '2026-03-15',
      confidence: 0.98,
      page: 1,
      bbox: [0.65, 0.14, 0.92, 0.18],
      confirmed: true,
    },
    client_name: {
      value: 'Société Marocaine de Commerce',
      confidence: 0.95,
      page: 1,
      bbox: [0.05, 0.20, 0.48, 0.24],
      confirmed: true,
    },
    total_ht: {
      value: '1000.00',
      confidence: 0.99,
      page: 1,
      bbox: [0.60, 0.70, 0.95, 0.74],
      confirmed: false, // à confirmer
    },
    total_vat: {
      value: '200.00',
      confidence: 0.98,
      page: 1,
      bbox: [0.60, 0.75, 0.95, 0.79],
      confirmed: true,
    },
    total_ttc: {
      value: '1200.00',
      confidence: 0.99,
      page: 1,
      bbox: [0.60, 0.81, 0.95, 0.86],
      confirmed: false, // à confirmer
    },
    payment_method: {
      value: 'virement',
      confidence: 0.95,
      page: 1,
      bbox: null,
      confirmed: true,
    },
  });

  const handleSave = async (updatedFields: Record<string, FieldExtraction>) => {
    // Simulate network delay and immutable audit log update
    await new Promise((resolve) => setTimeout(resolve, 400));
    setFields(updatedFields);
  };

  return (
    <div className="flex flex-col h-screen bg-paper">
      {/* Return Navigation */}
      <div className="border-b border-line px-4 py-2 bg-surface flex items-center justify-between text-xs">
        <Link
          to="/app/documents"
          className="flex items-center gap-1.5 text-ink-2 hover:text-ink font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Retour à la liste des documents</span>
        </Link>
        <div className="text-ink-2">
          Dossier : <span className="font-semibold text-ink">Mars 2026</span>
        </div>
      </div>

      {/* Main DocumentViewer */}
      <div className="flex-1 overflow-hidden">
        <DocumentViewer
          documentId={id}
          filename="FACTURE_ATLAS_MARS_2026.pdf"
          docType="Facture d'achat"
          pageCount={2}
          pages={[
            { pageNumber: 1, width: 800, height: 1131 },
            { pageNumber: 2, width: 800, height: 1131 },
          ]}
          initialFields={fields}
          onSave={handleSave}
        />
      </div>
    </div>
  );
}
