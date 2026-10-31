-- 004_fx_rates.up.sql (run as avenel_owner)

CREATE TABLE fx_rates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  rate_date date NOT NULL,
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  rate numeric(18,8) NOT NULL CHECK (rate > 0),
  source text NOT NULL CHECK (source IN ('bam_fixing','manual','imported')),
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES users(id),
  UNIQUE (tenant_id, rate_date, currency)
);

CREATE INDEX fx_rates_lookup_idx ON fx_rates (tenant_id, currency, rate_date);

ALTER TABLE fx_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE fx_rates FORCE ROW LEVEL SECURITY;

CREATE POLICY fx_rates_tenant_isolation ON fx_rates
  FOR ALL
  USING (tenant_id = app.current_tenant())
  WITH CHECK (tenant_id = app.current_tenant());

GRANT SELECT, INSERT, UPDATE, DELETE ON fx_rates TO avenel_app;

-- Expand client_tax_mappings direction check to allow 'rounding'
ALTER TABLE client_tax_mappings DROP CONSTRAINT IF EXISTS client_tax_mappings_direction_check;
ALTER TABLE client_tax_mappings ADD CONSTRAINT client_tax_mappings_direction_check
  CHECK (direction IN ('purchase','sale','fixed_asset','withholding','rounding'));
