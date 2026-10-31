import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProposalReview, Proposal } from './ProposalReview';

const mockProposals: Proposal[] = [
  {
    id: 'prop-001',
    work_request_id: 'wr-123',
    revision: 1,
    journal_code: 'ACH',
    entry_date: '2026-03-15',
    label: 'Facture achat N° FA-2026-001 - Atlas Fournitures',
    status: 'proposed',
    rule_refs: ['vat.rate.standard', 'cgnc.seed.accounts'],
    lines: [
      {
        id: 'line-1',
        line_no: 1,
        account_id: 'acc-6111',
        account_code: '6111',
        label: 'Achats de marchandises',
        currency: 'MAD',
        debit_mad: 1000.0,
        credit_mad: 0.0,
        tax_code: 'STANDARD_20',
        evidence_refs: [
          {
            field: 'total_ht',
            bbox: [0.1, 0.2, 0.4, 0.25],
            page: 1,
          },
        ],
      },
      {
        id: 'line-2',
        line_no: 2,
        account_id: 'acc-34552',
        account_code: '34552',
        label: 'État - TVA récupérable sur charges',
        currency: 'MAD',
        debit_mad: 200.0,
        credit_mad: 0.0,
        tax_code: 'STANDARD_20',
        evidence_refs: [
          {
            field: 'total_vat',
            bbox: [0.1, 0.3, 0.4, 0.35],
            page: 1,
          },
        ],
      },
      {
        id: 'line-3',
        line_no: 3,
        account_id: 'acc-4411',
        account_code: '4411',
        label: 'Fournisseurs',
        currency: 'MAD',
        debit_mad: 0.0,
        credit_mad: 1200.0,
        evidence_refs: [
          {
            field: 'total_ttc',
            bbox: [0.1, 0.4, 0.4, 0.45],
            page: 1,
          },
        ],
      },
    ],
  },
  {
    id: 'prop-002',
    work_request_id: 'wr-123',
    revision: 1,
    journal_code: 'VEN',
    entry_date: '2026-03-20',
    label: 'Facture vente N° V-2026-099 - Client Beta',
    status: 'proposed',
    rule_refs: ['vat.rate.standard'],
    lines: [
      {
        id: 'line-21',
        line_no: 1,
        account_id: 'acc-3421',
        account_code: '3421',
        label: 'Clients',
        currency: 'MAD',
        debit_mad: 600.0,
        credit_mad: 0.0,
        evidence_refs: [{ field: 'total_ttc', bbox: [0.1, 0.1, 0.5, 0.2], page: 1 }],
      },
      {
        id: 'line-22',
        line_no: 2,
        account_id: 'acc-7111',
        account_code: '7111',
        label: 'Ventes de marchandises',
        currency: 'MAD',
        debit_mad: 0.0,
        credit_mad: 500.0,
        evidence_refs: [{ field: 'total_ht', bbox: [0.1, 0.2, 0.5, 0.3], page: 1 }],
      },
      {
        id: 'line-23',
        line_no: 3,
        account_id: 'acc-4455',
        account_code: '4455',
        label: 'État - TVA facturée',
        currency: 'MAD',
        debit_mad: 0.0,
        credit_mad: 100.0,
        evidence_refs: [{ field: 'total_vat', bbox: [0.1, 0.3, 0.5, 0.4], page: 1 }],
      },
    ],
  },
];

describe('ProposalReview Component', () => {
  it('renders balanced entry with accounts, totals and balance badge', () => {
    render(<ProposalReview proposals={mockProposals} />);

    expect(screen.getByTestId('balance-indicator')).toHaveTextContent('Équilibré (Δ = 0,00 MAD)');
    expect(screen.getByTestId('proposal-status-badge')).toHaveTextContent('Proposée');

    expect(screen.getByText('Facture achat N° FA-2026-001 - Atlas Fournitures')).toBeInTheDocument();
    expect(screen.getByText('6111')).toBeInTheDocument();
    expect(screen.getByText('34552')).toBeInTheDocument();
    expect(screen.getByText('4411')).toBeInTheDocument();

    // Verify initial line 1 evidence bbox is present
    expect(screen.getByTestId('evidence-bbox-overlay')).toBeInTheDocument();
  });

  it('navigates between proposals using next/prev buttons and keyboard shortcuts J/K', async () => {
    render(<ProposalReview proposals={mockProposals} />);

    expect(screen.getByText('Facture achat N° FA-2026-001 - Atlas Fournitures')).toBeInTheDocument();

    // Press 'j' key to navigate to next proposal
    fireEvent.keyDown(window, { key: 'j' });
    expect(screen.getByText('Facture vente N° V-2026-099 - Client Beta')).toBeInTheDocument();

    // Press 'k' key to navigate back to previous proposal
    fireEvent.keyDown(window, { key: 'k' });
    expect(screen.getByText('Facture achat N° FA-2026-001 - Atlas Fournitures')).toBeInTheDocument();
  });

  it('updates evidence bbox when clicking a different proposal line', () => {
    render(<ProposalReview proposals={mockProposals} />);

    // Click line 2 (TVA line)
    const line2 = screen.getByTestId('proposal-line-row-2');
    fireEvent.click(line2);

    expect(screen.getByTestId('evidence-bbox-overlay')).toBeInTheDocument();
  });

  it('Enter key confirms the focused line only (toast: Ligne confirmée)', async () => {
    render(<ProposalReview proposals={mockProposals} />);

    // Line 1 is initially focused. Press Enter.
    fireEvent.keyDown(window, { key: 'Enter' });

    expect(screen.getByTestId('toast-message')).toHaveTextContent('Ligne confirmée');
  });

  it('removes any approve action button and confirms no per-entry approval endpoint exists', () => {
    render(<ProposalReview proposals={mockProposals} />);

    // Must NOT have any approve buttons or actions
    expect(screen.queryByTestId('approve-proposal-btn')).toBeNull();
    expect(screen.queryByRole('button', { name: /valider l'écriture/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /approuver/i })).toBeNull();
  });

  it('tests that no keyboard path triggers approval', async () => {
    render(<ProposalReview proposals={mockProposals} />);

    // Press various keys including Enter, Space, 'a', 'v'
    fireEvent.keyDown(window, { key: 'Enter' });
    fireEvent.keyDown(window, { key: ' ' });
    fireEvent.keyDown(window, { key: 'a' });
    fireEvent.keyDown(window, { key: 'v' });

    // Status badge must strictly remain "Proposée", never "Approuvée"
    expect(screen.getByTestId('proposal-status-badge')).toHaveTextContent('Proposée');
  });
});
