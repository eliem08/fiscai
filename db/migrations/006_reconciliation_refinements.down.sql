-- 006_reconciliation_refinements.down.sql (run as avenel_owner)

DROP TRIGGER IF EXISTS trg_set_match_item_status_on_insert ON reconciliation_match_items;
DROP FUNCTION IF EXISTS set_match_item_status_on_insert();

DROP TRIGGER IF EXISTS trg_sync_reconciliation_matches_status ON reconciliation_matches;
DROP FUNCTION IF EXISTS sync_match_items_status();

DROP INDEX IF EXISTS one_accepted_match_per_bank_line;
CREATE UNIQUE INDEX one_accepted_match_per_bank_line
  ON reconciliation_match_items (tenant_id, bank_transaction_id)
  WHERE bank_transaction_id IS NOT NULL;

ALTER TABLE reconciliation_match_items DROP COLUMN IF EXISTS match_status;

ALTER TABLE reconciliation_matches DROP CONSTRAINT IF EXISTS reconciliation_matches_difference_kind_check;
ALTER TABLE reconciliation_matches ADD CONSTRAINT reconciliation_matches_difference_kind_check
  CHECK (difference_kind IN ('vat_withheld','bank_fee','fx','rounding','unexplained'));

ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding','rounding','rounding_loss','rounding_gain'));
