import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  ReconciliationScreen,
  BankTransactionLine,
  ReconciliationMatch,
  ProposalSummary,
} from './ReconciliationScreen';

const mockBankTransactions: BankTransactionLine[] = [
  {
    id: 'tx-001',
    line_index: 1,
    booking_date: '2026-03-20',
    amount: 10500.0,
    currency: 'MAD',
    description: 'VIR CLIENT ATLAS RAS TVA',
  },
  {
    id: 'tx-002',
    line_index: 2,
    booking_date: '2026-03-22',
    amount: -12000.0,
    currency: 'MAD',
    description: 'VIR FOURNISSEUR BUREAU SERVICE',
  },
];

const mockProposals: ProposalSummary[] = [
  {
    id: 'prop-001',
    journal_code: 'VEN',
    entry_date: '2026-03-15',
    label: 'Facture vente N° V-2026-001 - Client Atlas',
    amount_ttc: 12000.0,
    vat_amount: 2000.0,
    counterparty_name: 'Client Atlas',
  },
  {
    id: 'prop-002',
    journal_code: 'ACH',
    entry_date: '2026-03-18',
    label: 'Facture achat N° FA-2026-042 - Fournisseur Bureau',
    amount_ttc: 12000.0,
    vat_amount: 2000.0,
    counterparty_name: 'Fournisseur Bureau',
  },
];

const mockMatches: ReconciliationMatch[] = [
  {
    id: 'match-001',
    status: 'proposed',
    score: 0.98,
    reasons: ['Retenue à la source de TVA détectée (75%)'],
    difference_mad: 1500.0,
    difference_kind: 'vat_withheld',
    items: [
      {
        id: 'item-1',
        bank_transaction_id: 'tx-001',
        amount_mad: 10500.0,
        bank_date: '2026-03-20',
        bank_desc: 'VIR CLIENT ATLAS RAS TVA',
      },
      {
        id: 'item-2',
        journal_proposal_id: 'prop-001',
        amount_mad: 12000.0,
        proposal_date: '2026-03-15',
        proposal_label: 'Facture vente N° V-2026-001 - Client Atlas',
      },
    ],
  },
  {
    id: 'match-002',
    status: 'proposed',
    score: 1.0,
    reasons: ['Montant identique'],
    difference_mad: 0.0,
    difference_kind: null,
    items: [
      {
        id: 'item-3',
        bank_transaction_id: 'tx-002',
        amount_mad: -12000.0,
        bank_date: '2026-03-22',
        bank_desc: 'VIR FOURNISSEUR BUREAU SERVICE',
      },
      {
        id: 'item-4',
        journal_proposal_id: 'prop-002',
        amount_mad: 12000.0,
        proposal_date: '2026-03-18',
        proposal_label: 'Facture achat N° FA-2026-042 - Fournisseur Bureau',
      },
    ],
  },
];

describe('ReconciliationScreen component', () => {
  it('renders bank lines and candidate matches correctly', () => {
    render(
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposals}
        matches={mockMatches}
        onAcceptMatch={vi.fn()}
        onRejectMatch={vi.fn()}
      />
    );

    expect(screen.getByText('Rapprochement bancaire')).toBeInTheDocument();
    expect(screen.getAllByText('VIR CLIENT ATLAS RAS TVA').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('VIR FOURNISSEUR BUREAU SERVICE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Retenue à la source de TVA détectée (75%)')).toBeInTheDocument();
    expect(screen.getByText('TVA retenue à la source')).toBeInTheDocument();
  });

  it('triggers onAcceptMatch when clicking Rapprocher button', () => {
    const onAccept = vi.fn();
    render(
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposals}
        matches={mockMatches}
        onAcceptMatch={onAccept}
        onRejectMatch={vi.fn()}
      />
    );

    const acceptBtn = screen.getByTestId('btn-accept-match-001');
    fireEvent.click(acceptBtn);
    expect(onAccept).toHaveBeenCalledWith('match-001');
  });

  it('triggers onRejectMatch when clicking Rejeter button', () => {
    const onReject = vi.fn();
    render(
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposals}
        matches={mockMatches}
        onAcceptMatch={vi.fn()}
        onRejectMatch={onReject}
      />
    );

    const rejectBtn = screen.getByTestId('btn-reject-match-001');
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith('match-001');
  });

  it('accepts match on Enter keypress', () => {
    const onAccept = vi.fn();
    render(
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposals}
        matches={mockMatches}
        onAcceptMatch={onAccept}
        onRejectMatch={vi.fn()}
      />
    );

    const screenContainer = screen.getByTestId('reconciliation-screen');
    fireEvent.keyDown(screenContainer, { key: 'Enter', code: 'Enter' });
    expect(onAccept).toHaveBeenCalledWith('match-001');
  });

  it('rejects match on Escape keypress', () => {
    const onReject = vi.fn();
    render(
      <ReconciliationScreen
        bankTransactions={mockBankTransactions}
        proposals={mockProposals}
        matches={mockMatches}
        onAcceptMatch={vi.fn()}
        onRejectMatch={onReject}
      />
    );

    const screenContainer = screen.getByTestId('reconciliation-screen');
    fireEvent.keyDown(screenContainer, { key: 'Escape', code: 'Escape' });
    expect(onReject).toHaveBeenCalledWith('match-001');
  });
});
