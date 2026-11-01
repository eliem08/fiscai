import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { QueueScreen, QueueRowItem } from '@/components/domain/QueueScreen';
import { ProposalReview, Proposal } from '@/components/domain/ProposalReview';
import { ReconciliationScreen, BankTransactionLine, ProposalSummary, ReconciliationMatch } from '@/components/domain/ReconciliationScreen';
import { ApprovalScreen, ApprovalWorkRequest, CurrentReviewer, ReviewIssueItem } from '@/components/domain/ApprovalScreen';
import { ExportScreen, ExportProfileSummary, ExportTarget } from '@/components/domain/ExportScreen';
import { PortalRequests, PortalRequestItem } from '@/components/domain/PortalRequests';
import { InternalMetricsScreen } from '@/components/domain/InternalMetricsScreen';
import { CheckCircle2, ArrowRight, ShieldCheck, FileSpreadsheet, Lock } from 'lucide-react';

// Sample data for Queue Screen
const mockQueueItems: QueueRowItem[] = [
  {
    id: 'wr-atlas-001',
    client_id: 'cl-atlas',
    company_name: 'Atlas Distribution SARL',
    period_code: '2026-09',
    documents_count: 142,
    status: 'awaiting_approval',
    status_label: 'À valider',
    issues_count: 3,
    blocking_issues_count: 0,
    due_date: '10 oct',
    assigned_to: 'S. Alami',
    needs_person: true,
  },
  {
    id: 'wr-riad-002',
    client_id: 'cl-riad',
    company_name: 'Riad Menara SARL',
    period_code: '2026-09',
    documents_count: 87,
    status: 'reviewing',
    status_label: 'Lecture',
    issues_count: 0,
    blocking_issues_count: 0,
    due_date: '12 oct',
    assigned_to: null,
    needs_person: false,
  },
  {
    id: 'wr-tanger-003',
    client_id: 'cl-tanger',
    company_name: 'Tanger Logistics SA',
    period_code: '2026-09',
    documents_count: 54,
    status: 'approved',
    status_label: 'Validé',
    issues_count: 0,
    blocking_issues_count: 0,
    due_date: '08 oct',
    assigned_to: 'K. Bennani',
    needs_person: false,
  },
];

// Sample data for Proposal Review
const mockProposals: Proposal[] = [
  {
    id: 'prop-ach-01',
    work_request_id: 'wr-atlas-001',
    revision: 2,
    journal_code: 'ACH',
    entry_date: '2026-09-12',
    label: 'Facture F-2026-0412 · Fournitures Bureau',
    status: 'proposed',
    rule_refs: ['vat.standard_rate', 'deductibility.standard'],
    lines: [
      {
        id: 'line-1',
        line_no: 1,
        account_id: 'acc-6111',
        account_code: '6111',
        label: 'Achats de marchandises',
        currency: 'MAD',
        debit_mad: 10000.0,
        credit_mad: 0.0,
        evidence_refs: [
          {
            field: 'total_ht',
            page: 1,
            bbox: [0.55, 0.70, 0.90, 0.74],
          },
        ],
      },
      {
        id: 'line-2',
        line_no: 2,
        account_id: 'acc-34552',
        account_code: '34552',
        label: 'TVA récupérable sur charges (20%)',
        currency: 'MAD',
        tax_code: 'TVA20',
        debit_mad: 2000.0,
        credit_mad: 0.0,
        evidence_refs: [
          {
            field: 'total_vat',
            page: 1,
            bbox: [0.55, 0.75, 0.90, 0.79],
          },
        ],
      },
      {
        id: 'line-3',
        line_no: 3,
        account_id: 'acc-4411',
        account_code: '4411',
        label: 'Fournisseurs - Papeterie Atlas',
        currency: 'MAD',
        debit_mad: 0.0,
        credit_mad: 12000.0,
        evidence_refs: [
          {
            field: 'total_ttc',
            page: 1,
            bbox: [0.55, 0.81, 0.90, 0.86],
          },
        ],
      },
    ],
  },
];

// Sample data for Reconciliation
const mockBankTransactions: BankTransactionLine[] = [
  {
    id: 'btx-001',
    line_index: 1,
    booking_date: '2026-09-15',
    value_date: '2026-09-15',
    amount: -12000.0,
    currency: 'MAD',
    description: 'VIR PAPETERIE ATLAS FAC 0412',
    external_reference: 'VIR-99812',
  },
  {
    id: 'btx-002',
    line_index: 2,
    booking_date: '2026-09-18',
    value_date: '2026-09-18',
    amount: 35000.0,
    currency: 'MAD',
    description: 'VIR CLIENT CASABLANCA SERVICES',
    external_reference: 'VIR-44120',
  },
];

const mockProposalSummaries: ProposalSummary[] = [
  {
    id: 'prop-ach-01',
    journal_code: 'ACH',
    entry_date: '2026-09-12',
    label: 'Facture F-2026-0412',
    amount_ttc: 12000.0,
    counterparty_name: 'Papeterie Atlas',
    invoice_number: 'F-2026-0412',
  },
];

const mockMatches: ReconciliationMatch[] = [
  {
    id: 'match-001',
    status: 'proposed',
    score: 0.99,
    reasons: ['Montant exact 12 000,00 MAD', 'Rapprochement libellé fournisseur'],
    difference_mad: 0.0,
    difference_kind: null,
    items: [
      {
        id: 'mi-1',
        bank_transaction_id: 'btx-001',
        amount_mad: 12000.0,
        bank_date: '2026-09-15',
        bank_desc: 'VIR PAPETERIE ATLAS FAC 0412',
      },
      {
        id: 'mi-2',
        journal_proposal_id: 'prop-ach-01',
        amount_mad: 12000.0,
        proposal_date: '2026-09-12',
        proposal_label: 'Facture F-2026-0412',
      },
    ],
  },
];

// Sample data for Approval Screen
const mockApprovalWorkRequest: ApprovalWorkRequest = {
  id: 'wr-pilot-001',
  client_entity_id: 'cl-atlas',
  legal_name: 'Atlas Distribution SARL',
  period_code: '2026-09',
  status: 'awaiting_approval',
  prepared_by: 'user-staff-1',
  prepared_by_name: 'Salma Alami (Collaboratrice)',
  requested_at: '2026-10-02',
  subject_hash: '9f8e7d6c5b4a3210fedcba9876543210abcdef0123456789abcdef0123456789',
  proposals_count: 24,
  total_debit_mad: 65400.0,
  total_credit_mad: 65400.0,
  open_blocking_issues_count: 0,
  open_warning_issues_count: 1,
  unacknowledged_review_issues_count: 0,
  single_person_policy: false,
};

const mockReviewIssues: ReviewIssueItem[] = [
  {
    id: 'iss-001',
    code: 'DOC_NOTE_MISSING',
    status: 'resolved',
    resolution: 'accepted_as_is',
    resolution_note: 'Note de frais validée par la direction.',
  },
];

const mockReviewer: CurrentReviewer = {
  user_id: 'user-expert-1',
  full_name: 'Mehdi Bennani',
  role: 'owner',
  professional_title: 'expert_comptable',
  professional_registration_no: 'OEC-45678',
};

// Sample data for Export Screen
const mockProfiles: ExportProfileSummary[] = [
  {
    id: 'prof-sage-csv',
    name: 'Sage 100 Coala / Comptabilité (CSV)',
    target: 'sage100_csv',
    encoding: 'cp1252',
    verified_round_trip_at: '2026-10-25T14:30:00Z',
  },
  {
    id: 'prof-odoo-csv',
    name: 'Odoo Enterprise (CSV)',
    target: 'odoo_csv',
    encoding: 'utf-8',
    verified_round_trip_at: null,
  },
];

// Sample data for Portal Requests
const mockPortalRequests: PortalRequestItem[] = [
  {
    id: 'pr-001',
    client_entity_id: 'cl-atlas',
    legal_name: 'Atlas Distribution SARL',
    code: 'INVOICE_MISSING',
    message: 'Prélèvement bancaire de 4 500,00 MAD du 14/09 sans justificatif joint.',
    prompt: 'Merci de téléverser la facture ou le contrat correspondant au débit TELECOM MAROC.',
    created_at: '2026-09-28T09:15:00Z',
  },
];

export function PilotDemoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const screen = searchParams.get('screen') || 'queue';

  // Interactive state for end-to-end journey demonstration
  const [journeyStep, setJourneyStep] = useState<number>(1);
  const [fieldCorrected, setFieldCorrected] = useState(false);
  const [issuesResolved, setIssuesResolved] = useState(false);
  const [matchAccepted, setMatchAccepted] = useState(false);
  const [exported, setExported] = useState(false);

  // Field edit state
  const [correctedIce, setCorrectedIce] = useState('001234567890123');

  // MFA check state
  const [mfaCode, setMfaCode] = useState('123456');

  if (screen === 'queue') {
    return <QueueScreen items={mockQueueItems} onNewDossier={() => setSearchParams({ screen: 'journey' })} />;
  }

  if (screen === 'review') {
    return <ProposalReview proposals={mockProposals} />;
  }

  if (screen === 'reconciliation') {
    return (
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposalSummaries}
        matches={mockMatches}
        onAcceptMatch={async () => {}}
        onRejectMatch={async () => {}}
      />
    );
  }

  if (screen === 'approval') {
    return (
      <ApprovalScreen
        workRequest={mockApprovalWorkRequest}
        reviewer={mockReviewer}
        reviewIssues={mockReviewIssues}
        onApprove={async () => {}}
        onReject={async () => {}}
      />
    );
  }

  if (screen === 'export') {
    return (
      <ExportScreen
        workRequestId="wr-pilot-001"
        approvalId="appr-pilot-001"
        clientName="Atlas Distribution SARL"
        periodCode="2026-09"
        approvedSubjectHash="9f8e7d6c5b4a3210fedcba9876543210abcdef0123456789abcdef0123456789"
        availableProfiles={mockProfiles}
        onGenerateExport={async (target: ExportTarget) => ({
          id: 'exp-pilot-001',
          work_request_id: 'wr-pilot-001',
          client_entity_id: 'cl-atlas',
          target,
          encoding: 'cp1252',
          status: 'ready',
          file_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          evidence_pack_sha256: 'a1b2c3d4e5f67890123456789012345678901234567890123456789012345678',
          subject_hash: '9f8e7d6c5b4a3210fedcba9876543210abcdef0123456789abcdef0123456789',
          created_at: new Date().toISOString(),
        })}
        onDownloadFile={async () => {}}
        onDownloadEvidencePack={async () => {}}
      />
    );
  }

  if (screen === 'portal') {
    return <PortalRequests requests={mockPortalRequests} onAnswerRequest={async () => {}} />;
  }

  if (screen === 'metrics') {
    const roleParam = (searchParams.get('role') as any) || 'owner';
    return <InternalMetricsScreen currentUserRole={roleParam} />;
  }

  // Monthly Journey End-to-End Orchestrator
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans" data-testid="pilot-journey-container">
      {/* Journey Navigation Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">Cycle Mensuel Pilote</span>
          <h1 className="text-xl font-bold text-slate-900 mt-0.5">Dossier Comptable Complet · Octobre 2026</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono bg-slate-100 text-slate-700 px-3 py-1 rounded-full">
            Étape {journeyStep} / 10
          </span>
        </div>
      </header>

      {/* Main Stepper Body */}
      <main className="flex-1 p-6 max-w-5xl mx-auto w-full">
        {journeyStep === 1 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-client-creation">
            <h2 className="text-base font-bold text-slate-900">1. Création de l'entité cliente (SARL)</h2>
            <p className="text-xs text-slate-500">Renseignement des identifiants légaux marocains vérifiés.</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <label htmlFor="company-name" className="block font-medium text-slate-700 mb-1">Raison sociale</label>
                <input id="company-name" type="text" readOnly value="Atlas Distribution SARL" className="w-full p-2 border border-slate-200 rounded bg-slate-50" />
              </div>
              <div>
                <label htmlFor="company-form" className="block font-medium text-slate-700 mb-1">Forme juridique</label>
                <input id="company-form" type="text" readOnly value="SARL" className="w-full p-2 border border-slate-200 rounded bg-slate-50" />
              </div>
              <div>
                <label htmlFor="company-ice" className="block font-medium text-slate-700 mb-1">ICE (15 chiffres)</label>
                <input id="company-ice" type="text" readOnly value="001523456000089" className="w-full p-2 border border-slate-200 rounded bg-slate-50 font-mono" />
              </div>
              <div>
                <label htmlFor="company-if" className="block font-medium text-slate-700 mb-1">Identifiant Fiscal (IF)</label>
                <input id="company-if" type="text" readOnly value="40239102" className="w-full p-2 border border-slate-200 rounded bg-slate-50 font-mono" />
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(2);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5"
                data-testid="btn-create-client"
              >
                <span>Créer le client</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 2 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-chart-import">
            <h2 className="text-base font-bold text-slate-900">2. Import du Plan Comptable CGNC</h2>
            <p className="text-xs text-slate-500">Normalisation comptable marocaine selon le Code Général de Normalisation Comptable.</p>
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1">
              <p className="font-semibold text-slate-900">Pack juridictionnel : Maroc (CGNC 1989)</p>
              <p>Comptes de charges : Classe 6 (6111, 6141, 6147...)</p>
              <p>Comptes de trésorerie & tiers : Classes 4 et 5 (4411, 34552, 5141...)</p>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(3);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5"
                data-testid="btn-import-chart"
              >
                <span>Importer le plan CGNC</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 3 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-open-period">
            <h2 className="text-base font-bold text-slate-900">3. Ouverture de la période comptable</h2>
            <p className="text-xs text-slate-500">Création de la demande de travail mensuelle (Work Request).</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <label htmlFor="period-code" className="block font-medium text-slate-700 mb-1">Période fiscale</label>
                <input id="period-code" type="text" readOnly value="2026-10 (Octobre 2026)" className="w-full p-2 border border-slate-200 rounded bg-slate-50" />
              </div>
              <div>
                <label htmlFor="period-due-date" className="block font-medium text-slate-700 mb-1">Date d'échéance déclarative</label>
                <input id="period-due-date" type="text" readOnly value="2026-11-20" className="w-full p-2 border border-slate-200 rounded bg-slate-50" />
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(4);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5"
                data-testid="btn-open-period"
              >
                <span>Ouvrir la période</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 4 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-upload-documents">
            <h2 className="text-base font-bold text-slate-900">4. Téléversement des pièces justificatives & relevé</h2>
            <p className="text-xs text-slate-500">Factures d'achat, de vente et relevé bancaire Attijariwafa Bank.</p>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded">
                <span className="font-medium text-slate-800">FAC-2026-0891_Fournisseur_Papeterie.pdf</span>
                <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded">Prêt pour extraction</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded">
                <span className="font-medium text-slate-800">Releve_Bancaire_Attijariwafa_Octobre2026.pdf</span>
                <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded">Prêt pour rapprochement</span>
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(5);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5"
                data-testid="btn-upload-files"
              >
                <span>Lancer le traitement et la revue</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 5 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-review-correction">
            <h2 className="text-base font-bold text-slate-900">5. Revue et correction d'un champ (DocumentViewer)</h2>
            <p className="text-xs text-slate-500">Mise en évidence visuelle de la zone source et confirmation manuelle du champ.</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-slate-50 rounded border border-slate-200 flex flex-col justify-center items-center">
                <div className="w-full h-32 border-2 border-dashed border-indigo-300 rounded flex items-center justify-center relative bg-white">
                  <div className="absolute top-4 left-6 px-3 py-1 bg-indigo-50 border border-indigo-400 rounded text-[11px] font-mono text-indigo-900" data-testid="mock-bbox-overlay">
                    ICE : {correctedIce}
                  </div>
                  <span className="text-slate-400 text-[10px]">Zone bbox [0.05, 0.08, 0.35, 0.11]</span>
                </div>
              </div>
              <div className="space-y-3">
                <div>
                  <label htmlFor="field-supplier-ice" className="block font-medium text-slate-700 mb-1">
                    ICE Fournisseur (à confirmer)
                  </label>
                  <input
                    id="field-supplier-ice"
                    type="text"
                    value={correctedIce}
                    onChange={(e) => setCorrectedIce(e.target.value)}
                    className="w-full p-2 border border-slate-300 rounded font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                    data-testid="input-correct-ice"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setFieldCorrected(true)}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded"
                  data-testid="btn-confirm-field"
                >
                  {fieldCorrected ? 'Champ confirmé ✓' : 'Confirmer le champ (Entrée)'}
                </button>
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={!fieldCorrected}
                onClick={() => setJourneyStep(6)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5 disabled:opacity-50"
                data-testid="btn-proceed-issues"
              >
                <span>Étape suivante : Anomalies</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 6 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-resolve-issues">
            <h2 className="text-base font-bold text-slate-900">6. Contrôle qualité et acquittement des anomalies</h2>
            <p className="text-xs text-slate-500">Zéro anomalie bloquante. Justification formelle de l'anomalie de revue.</p>
            <div className="p-4 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900 flex items-center justify-between">
              <div>
                <span className="font-mono font-bold bg-amber-200 text-amber-900 px-2 py-0.5 rounded">DOC_NOTE_MISSING</span>
                <p className="mt-1">Note de frais de mission sans ordre de mission attaché.</p>
              </div>
              <button
                type="button"
                onClick={() => setIssuesResolved(true)}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded"
                data-testid="btn-acknowledge-issue"
              >
                {issuesResolved ? 'Anomalie acquittée ✓' : 'Acquitter (Justification acceptée)'}
              </button>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={!issuesResolved}
                onClick={() => setJourneyStep(7)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5 disabled:opacity-50"
                data-testid="btn-proceed-reconciliation"
              >
                <span>Étape suivante : Rapprochement</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 7 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-reconciliation">
            <h2 className="text-base font-bold text-slate-900">7. Rapprochement bancaire et acceptation de matching</h2>
            <p className="text-xs text-slate-500">Association de la ligne de débit bancaire à la facture d'achat.</p>
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
              <div>
                <p className="font-semibold text-slate-900">Débit : -12 000,00 MAD · VIR PAPETERIE ATLAS FAC 0412</p>
                <p className="text-slate-500 mt-0.5">Facture F-2026-0412 (12 000,00 MAD TTC) · Score 99%</p>
              </div>
              <button
                type="button"
                onClick={() => setMatchAccepted(true)}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded"
                data-testid="btn-accept-match"
              >
                {matchAccepted ? 'Rapprochement validé ✓' : 'Accepter le rapprochement'}
              </button>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={!matchAccepted}
                onClick={() => setJourneyStep(8)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5 disabled:opacity-50"
                data-testid="btn-proceed-staff-request"
              >
                <span>Étape suivante : Demande de validation</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 8 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-staff-request">
            <h2 className="text-base font-bold text-slate-900">8. Demande de validation initiée par le collaborateur</h2>
            <p className="text-xs text-slate-500">Rôle : `staff` (Salma Alami). Soumission à l'associé pour approbation.</p>
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1">
              <p>Écritures prêtes : 24 propositions équilibrées (65 400,00 MAD Débit = Crédit)</p>
              <p>Empreinte SHA-256 du dossier calculée.</p>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(9);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded flex items-center gap-1.5"
                data-testid="btn-request-approval"
              >
                <span>Demander la validation</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {journeyStep === 9 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-accountant-approval">
            <h2 className="text-base font-bold text-slate-900">9. Approbation formelle par l'Expert-Comptable avec MFA</h2>
            <p className="text-xs text-slate-500">Rôle : `owner`, Titre : `expert_comptable`, Inscription OEC : `OEC-45678`.</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded">
                <span className="text-slate-500 block mb-1">Réviseur habilité</span>
                <span className="font-bold text-slate-900">Mehdi Bennani (Expert-Comptable Diplômé)</span>
                <span className="block text-slate-600 font-mono mt-0.5">N° Ordre : OEC-45678</span>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded">
                <label htmlFor="mfa-token" className="text-slate-500 block mb-1 font-medium">Code MFA (Time-based OTP)</label>
                <input
                  id="mfa-token"
                  type="text"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  className="w-full p-1.5 border border-slate-300 rounded font-mono text-center font-bold tracking-widest text-slate-900"
                  data-testid="input-mfa-code"
                />
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setJourneyStep(10);
                }}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded flex items-center gap-1.5 shadow-sm"
                data-testid="btn-approve-dossier"
              >
                <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                <span>Valider le dossier</span>
              </button>
            </div>
          </div>
        )}

        {journeyStep === 10 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4" data-testid="step-export">
            <h2 className="text-base font-bold text-slate-900">10. Exportation Sage 100 CSV & Pack de Preuves</h2>
            <p className="text-xs text-slate-500">Génération des écritures comptables Sage 100 et téléchargement de l'archive ZIP probante.</p>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded space-y-2">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-indigo-600" aria-hidden="true" />
                  <span className="font-bold text-slate-900">Écritures Sage 100 (CSV)</span>
                </div>
                <p className="text-slate-500 text-[11px]">Format CP1252, délimiteur point-virgule, balises de pièces attachées.</p>
                <button
                  type="button"
                  onClick={() => setExported(true)}
                  className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded text-xs"
                  data-testid="btn-generate-sage-csv"
                >
                  {exported ? 'Écritures Sage générées ✓' : 'Générer Sage 100 CSV'}
                </button>
              </div>
              <div className="p-4 bg-slate-50 border border-slate-200 rounded space-y-2">
                <div className="flex items-center gap-2">
                  <Lock className="w-4 h-4 text-emerald-600" aria-hidden="true" />
                  <span className="font-bold text-slate-900">Dossier Probant (ZIP)</span>
                </div>
                <p className="text-slate-500 text-[11px]">Archive scellée SHA-256 avec manifest.json, pièces originales et journal.</p>
                <button
                  type="button"
                  disabled={!exported}
                  onClick={() => {}}
                  className="w-full py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded text-xs disabled:opacity-50"
                  data-testid="btn-download-evidence-pack"
                >
                  Télécharger le pack de preuves
                </button>
              </div>
            </div>
            {exported && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded flex items-center gap-2" data-testid="export-success-banner">
                <ShieldCheck className="w-4 h-4 text-emerald-600" aria-hidden="true" />
                <span>Cycle mensuel achevé avec succès. Empreinte validée et archivée de façon irrévocable.</span>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
