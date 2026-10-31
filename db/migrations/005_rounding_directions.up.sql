-- 005_rounding_directions.up.sql (run as avenel_owner)

-- Expand client_tax_mappings direction check to allow 'rounding_loss' and 'rounding_gain'
ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding','rounding','rounding_loss','rounding_gain'));
