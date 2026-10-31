-- 004_fx_rates.down.sql (run as avenel_owner)

DROP TABLE IF EXISTS fx_rates CASCADE;

DELETE FROM client_tax_mappings WHERE direction = 'rounding';

ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding'));
