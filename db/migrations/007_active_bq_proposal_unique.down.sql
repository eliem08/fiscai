-- Migration 007 Down: Drop one active BQ proposal unique index

DROP INDEX IF EXISTS one_active_bq_proposal_per_bank_transaction;

