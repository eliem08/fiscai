-- Migration 007: Enforce at most one active BQ proposal per bank transaction
-- Rule: Every bank transaction has at most one active journal proposal ('proposed', 'edited', 'approved').
-- Unmatched -> suspense proposal; on match accepted -> superseded by counterparty proposal in same tx;
-- on match rejected -> restored as suspense proposal revision.

CREATE UNIQUE INDEX one_active_bq_proposal_per_bank_transaction
ON journal_proposals (tenant_id, source_bank_transaction_id)
WHERE source_bank_transaction_id IS NOT NULL AND status IN ('proposed', 'edited', 'approved');

