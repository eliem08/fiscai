-- 006_reconciliation_refinements.up.sql (run as avenel_owner)

-- 1. Add match_status to reconciliation_match_items
ALTER TABLE reconciliation_match_items
  ADD COLUMN match_status text NOT NULL DEFAULT 'proposed'
  CHECK (match_status IN ('proposed','accepted','rejected','superseded'));

-- 2. Backfill existing items with parent match status
UPDATE reconciliation_match_items rmi
SET match_status = rm.status
FROM reconciliation_matches rm
WHERE rmi.match_id = rm.id;

-- 3. Trigger to keep match_status in sync with reconciliation_matches.status
CREATE OR REPLACE FUNCTION sync_match_items_status()
RETURNS trigger AS $$
BEGIN
  UPDATE reconciliation_match_items
  SET match_status = NEW.status
  WHERE match_id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_reconciliation_matches_status ON reconciliation_matches;
CREATE TRIGGER trg_sync_reconciliation_matches_status
AFTER UPDATE OF status ON reconciliation_matches
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION sync_match_items_status();

-- 4. Trigger to ensure inserted items inherit match_status
CREATE OR REPLACE FUNCTION set_match_item_status_on_insert()
RETURNS trigger AS $$
BEGIN
  IF NEW.match_status IS NULL OR NEW.match_status = 'proposed' THEN
    SELECT status INTO NEW.match_status
    FROM reconciliation_matches
    WHERE id = NEW.match_id;
    IF NEW.match_status IS NULL THEN
      NEW.match_status := 'proposed';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_match_item_status_on_insert ON reconciliation_match_items;
CREATE TRIGGER trg_set_match_item_status_on_insert
BEFORE INSERT ON reconciliation_match_items
FOR EACH ROW
EXECUTE FUNCTION set_match_item_status_on_insert();

-- 5. Replace unique index: allow multiple proposed/rejected candidates, enforce uniqueness ONLY on accepted
DROP INDEX IF EXISTS one_accepted_match_per_bank_line;
CREATE UNIQUE INDEX one_accepted_match_per_bank_line
  ON reconciliation_match_items (tenant_id, bank_transaction_id)
  WHERE bank_transaction_id IS NOT NULL AND match_status = 'accepted';

-- 6. Expand difference_kind in reconciliation_matches to include 'withholding_other'
ALTER TABLE reconciliation_matches DROP CONSTRAINT IF EXISTS reconciliation_matches_difference_kind_check;
ALTER TABLE reconciliation_matches ADD CONSTRAINT reconciliation_matches_difference_kind_check
  CHECK (difference_kind IN ('vat_withheld','bank_fee','fx','rounding','withholding_other','unexplained'));

-- 7. Expand client_tax_mappings direction check to allow 'bank_fee' and 'suspense'
ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding','rounding','rounding_loss','rounding_gain','bank_fee','suspense'));
