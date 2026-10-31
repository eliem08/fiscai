-- 002_rls.up.sql (run as avenel_owner)

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'avenel_app') THEN
    CREATE ROLE avenel_app;
  END IF;
END $$;

DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT c.relname FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
    WHERE n.nspname = 'public' AND c.relkind = 'r'
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'DROP POLICY IF EXISTS %I ON %I',
      t || '_tenant', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I USING (tenant_id = app.current_tenant()) WITH CHECK (tenant_id = app.current_tenant())',
      t || '_tenant', t);
  END LOOP;
END $$;

-- tenants: a session sees only its own tenant row
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenants_self ON tenants;
CREATE POLICY tenants_self ON tenants USING (id = app.current_tenant());

GRANT USAGE ON SCHEMA public, app TO avenel_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO avenel_app;
GRANT SELECT ON jurisdiction_tax_codes TO avenel_app;
REVOKE INSERT, UPDATE, DELETE ON jurisdiction_tax_codes FROM avenel_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO avenel_app;
-- DELETE is granted per table only where the domain needs it (draft lines, idempotency cleanup):
GRANT DELETE ON journal_lines, idempotency_keys TO avenel_app;
