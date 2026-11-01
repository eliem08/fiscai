import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ApprovalScreen, ApprovalWorkRequest, CurrentReviewer } from './ApprovalScreen';
import { ExportScreen, ExportProfileSummary, ExportResult } from './ExportScreen';
import { PortalRequests, PortalRequestItem } from './PortalRequests';

const mockWorkRequest: ApprovalWorkRequest = {
  id: 'wr-123',
  client_entity_id: 'cl-456',
  legal_name: 'Atlas Trading SARL',
  period_code: '2026-09',
  status: 'awaiting_approval',
  prepared_by: 'user-preparer-1',
  prepared_by_name: 'Karim Bennani',
  requested_at: '2026-10-02',
  subject_hash: 'a1b2c3d4e5f67890123456789012345678901234567890123456789012345678',
  proposals_count: 14,
  total_debit_mad: 45000.0,
  total_credit_mad: 45000.0,
  open_blocking_issues_count: 0,
  open_warning_issues_count: 1,
};

const mockReviewer: CurrentReviewer = {
  user_id: 'user-decider-2',
  full_name: 'Mehdi Alami',
  role: 'owner',
  professional_title: 'expert_comptable',
  professional_registration_no: 'OEC-45678',
};

describe('Phase 5 UI Components', () => {
  describe('ApprovalScreen', () => {
    it('renders dossier metadata, balanced totals, and allows approval when eligible', async () => {
      const onApprove = vi.fn().mockResolvedValue(undefined);
      const onReject = vi.fn().mockResolvedValue(undefined);

      render(
        <ApprovalScreen
          workRequest={mockWorkRequest}
          reviewer={mockReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      expect(screen.getByText('Atlas Trading SARL')).toBeInTheDocument();
      expect(screen.getByText('Période 2026-09')).toBeInTheDocument();
      expect(screen.getByText('Préparé par Karim Bennani')).toBeInTheDocument();
      expect(screen.getByText('Équilibré')).toBeInTheDocument();

      const approveBtn = screen.getByRole('button', { name: /Valider le dossier/i });
      expect(approveBtn).not.toBeDisabled();

      fireEvent.click(approveBtn);
      await waitFor(() => {
        expect(onApprove).toHaveBeenCalledWith(
          expect.any(String),
          mockWorkRequest.subject_hash,
        );
      });
      expect(screen.getByText('Dossier validé')).toBeInTheDocument();
    });

    it('disables approval button when reviewer is the preparer (segregation of duties)', () => {
      const onApprove = vi.fn();
      const onReject = vi.fn();

      const preparerReviewer: CurrentReviewer = {
        ...mockReviewer,
        user_id: 'user-preparer-1', // Same as workRequest.prepared_by
      };

      render(
        <ApprovalScreen
          workRequest={mockWorkRequest}
          reviewer={preparerReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      expect(screen.getByText(/Ségrégation des fonctions requise/i)).toBeInTheDocument();
      const approveBtn = screen.getByRole('button', { name: /Valider le dossier/i });
      expect(approveBtn).toBeDisabled();
    });

    it('allows approval when reviewer is preparer if single_person_policy is true', () => {
      const onApprove = vi.fn();
      const onReject = vi.fn();

      const preparerReviewer: CurrentReviewer = {
        ...mockReviewer,
        user_id: 'user-preparer-1',
      };

      render(
        <ApprovalScreen
          workRequest={{ ...mockWorkRequest, single_person_policy: true }}
          reviewer={preparerReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      expect(screen.getByText(/Politique dérogatoire active/i)).toBeInTheDocument();
      const approveBtn = screen.getByRole('button', { name: /Valider le dossier/i });
      expect(approveBtn).not.toBeDisabled();
    });

    it('disables approval when unacknowledged review issues exist', () => {
      const onApprove = vi.fn();
      const onReject = vi.fn();

      render(
        <ApprovalScreen
          workRequest={{ ...mockWorkRequest, unacknowledged_review_issues_count: 1 }}
          reviewer={mockReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      expect(screen.getByText(/1 anomalie\(s\) de revue en attente d'acquittement/i)).toBeInTheDocument();
      const approveBtn = screen.getByRole('button', { name: /Valider le dossier/i });
      expect(approveBtn).toBeDisabled();
    });

    it('disables approval when blocking issues exist or totals are unbalanced', () => {
      const onApprove = vi.fn();
      const onReject = vi.fn();

      const invalidWorkRequest: ApprovalWorkRequest = {
        ...mockWorkRequest,
        open_blocking_issues_count: 2,
        total_credit_mad: 42000.0, // Unbalanced
      };

      render(
        <ApprovalScreen
          workRequest={invalidWorkRequest}
          reviewer={mockReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      expect(screen.getByText('Déséquilibré')).toBeInTheDocument();
      expect(screen.getByText(/2 anomalie\(s\) bloquante\(s\)/i)).toBeInTheDocument();
      const approveBtn = screen.getByRole('button', { name: /Valider le dossier/i });
      expect(approveBtn).toBeDisabled();
    });

    it('allows rejection with a mandatory reason in modal', async () => {
      const onApprove = vi.fn();
      const onReject = vi.fn().mockResolvedValue(undefined);

      render(
        <ApprovalScreen
          workRequest={mockWorkRequest}
          reviewer={mockReviewer}
          onApprove={onApprove}
          onReject={onReject}
        />,
      );

      const rejectBtn = screen.getByRole('button', { name: /Refuser le dossier/i });
      fireEvent.click(rejectBtn);

      expect(screen.getByText('Motif du refus')).toBeInTheDocument();
      const textarea = screen.getByPlaceholderText(/Écart non justifié/i);
      fireEvent.change(textarea, { target: { value: 'Pièce justificative illisible sur ligne 3' } });

      const confirmRejectBtn = screen.getByRole('button', { name: /Confirmer le refus/i });
      fireEvent.click(confirmRejectBtn);

      await waitFor(() => {
        expect(onReject).toHaveBeenCalledWith('Pièce justificative illisible sur ligne 3');
      });
      expect(screen.getByText('Dossier refusé')).toBeInTheDocument();
    });
  });

  describe('ExportScreen', () => {
    const mockProfiles: ExportProfileSummary[] = [
      { id: 'prof-1', name: 'Sage 100 CSV', target: 'sage100_csv', encoding: 'cp1252', verified_round_trip_at: '2026-10-01' },
      { id: 'prof-2', name: 'Sage 100 PNM', target: 'sage100_pnm', encoding: 'cp1252' },
      { id: 'prof-3', name: 'Odoo CSV', target: 'odoo_csv', encoding: 'utf-8' },
    ];

    const mockExportResult: ExportResult = {
      id: 'exp-999',
      work_request_id: 'wr-123',
      client_entity_id: 'cl-456',
      target: 'sage100_csv',
      encoding: 'cp1252',
      status: 'ready',
      file_sha256: 'f1e2d3c4b5a67890123456789012345678901234567890123456789012345678',
      evidence_pack_sha256: '9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba',
      subject_hash: 'a1b2c3d4e5f67890123456789012345678901234567890123456789012345678',
      created_at: '2026-10-02T14:00:00Z',
    };

    it('renders target options, generates export, and displays verified hash & download buttons', async () => {
      const onGenerate = vi.fn().mockResolvedValue(mockExportResult);
      const onDownloadFile = vi.fn().mockResolvedValue(undefined);
      const onDownloadPack = vi.fn().mockResolvedValue(undefined);

      render(
        <ExportScreen
          workRequestId="wr-123"
          approvalId="app-789"
          clientName="Atlas Trading SARL"
          periodCode="2026-09"
          approvedSubjectHash="a1b2c3d4e5f67890123456789012345678901234567890123456789012345678"
          availableProfiles={mockProfiles}
          onGenerateExport={onGenerate}
          onDownloadFile={onDownloadFile}
          onDownloadEvidencePack={onDownloadPack}
        />,
      );

      expect(screen.getByText('Sage 100 (CSV)')).toBeInTheDocument();
      expect(screen.getByText('Sage 100 (PNM)')).toBeInTheDocument();
      expect(screen.getByText('Odoo (CSV)')).toBeInTheDocument();

      const genBtn = screen.getByRole('button', { name: /Générer l'export et le pack de preuves/i });
      fireEvent.click(genBtn);

      await waitFor(() => {
        expect(onGenerate).toHaveBeenCalledWith('sage100_csv', 'prof-1');
      });

      expect(screen.getByText('Empreinte vérifiée')).toBeInTheDocument();

      const downloadFileBtn = screen.getByRole('button', { name: /Télécharger les écritures/i });
      fireEvent.click(downloadFileBtn);
      expect(onDownloadFile).toHaveBeenCalledWith('exp-999');

      const downloadPackBtn = screen.getByRole('button', { name: /Télécharger le pack de preuves/i });
      fireEvent.click(downloadPackBtn);
      expect(onDownloadPack).toHaveBeenCalledWith('exp-999');
    });

    it('displays error banner if hash mismatch is rejected by the server', async () => {
      const onGenerate = vi.fn().mockRejectedValue(new Error('Le dossier a changé depuis la validation. Demandez une nouvelle validation.'));

      render(
        <ExportScreen
          workRequestId="wr-123"
          approvalId="app-789"
          clientName="Atlas Trading SARL"
          periodCode="2026-09"
          approvedSubjectHash="approved_hash_123"
          availableProfiles={mockProfiles}
          onGenerateExport={onGenerate}
          onDownloadFile={vi.fn()}
          onDownloadEvidencePack={vi.fn()}
        />,
      );

      const genBtn = screen.getByRole('button', { name: /Générer l'export et le pack de preuves/i });
      fireEvent.click(genBtn);

      await waitFor(() => {
        expect(screen.getByText(/Le dossier a changé depuis la validation/i)).toBeInTheDocument();
      });
    });

    it('displays unverified software warning when profile has no verified round trip', () => {
      const unverifiedProfiles: ExportProfileSummary[] = [
        { id: 'prof-unverified', name: 'Sage 100 CSV', target: 'sage100_csv', encoding: 'cp1252', verified_round_trip_at: null },
      ];

      render(
        <ExportScreen
          workRequestId="wr-123"
          approvalId="app-789"
          clientName="Atlas Trading SARL"
          periodCode="2026-09"
          approvedSubjectHash="approved_hash_123"
          availableProfiles={unverifiedProfiles}
          onGenerateExport={vi.fn()}
          onDownloadFile={vi.fn()}
          onDownloadEvidencePack={vi.fn()}
        />,
      );

      expect(screen.getByText('Format non vérifié sur votre logiciel')).toBeInTheDocument();
    });
  });

  describe('PortalRequests', () => {
    const mockRequests: PortalRequestItem[] = [
      {
        id: 'issue-1',
        client_entity_id: 'cl-456',
        legal_name: 'Atlas Trading SARL',
        code: 'MISSING_INVOICE_ATTACHMENT',
        message: 'Ligne bancaire sans justificatif de dépense',
        prompt: 'Veuillez téléverser la facture correspondant au débit de 1 200 MAD du 15/09/2026.',
        created_at: '2026-09-20T10:00:00Z',
      },
    ];

    it('renders pending client requests and allows client to submit an answer', async () => {
      const onAnswer = vi.fn().mockResolvedValue(undefined);

      render(
        <PortalRequests
          requests={mockRequests}
          onAnswerRequest={onAnswer}
        />,
      );

      expect(screen.getByText('MISSING_INVOICE_ATTACHMENT')).toBeInTheDocument();
      expect(screen.getByText(/Veuillez téléverser la facture/i)).toBeInTheDocument();

      const answerBtn = screen.getByRole('button', { name: /Répondre à la demande/i });
      fireEvent.click(answerBtn);

      expect(screen.getByText('Répondre au cabinet comptable')).toBeInTheDocument();
      const textarea = screen.getByPlaceholderText(/Indiquez ici vos précisions/i);
      fireEvent.change(textarea, { target: { value: 'Facture retrouvée et transmise par email ce matin.' } });

      const sendBtn = screen.getByRole('button', { name: /Envoyer la réponse/i });
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(onAnswer).toHaveBeenCalledWith(
          'issue-1',
          'Facture retrouvée et transmise par email ce matin.',
        );
      });
      expect(screen.getByText('Réponse transmise au cabinet')).toBeInTheDocument();
    });

    it('renders empty state when there are no pending requests', () => {
      render(
        <PortalRequests
          requests={[]}
          onAnswerRequest={vi.fn()}
        />,
      );

      expect(screen.getByText('Aucune demande en attente')).toBeInTheDocument();
    });
  });
});

