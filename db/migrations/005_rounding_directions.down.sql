-- 005_rounding_directions.down.sql (run as avenel_owner)

DELETE FROM client_tax_mappings WHERE direction IN ('rounding_loss', 'rounding_gain');

ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding','rounding'));
