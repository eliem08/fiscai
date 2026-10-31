-- 001_core.up.sql (run as avenel_owner)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_tenant() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.user_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app.touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- Identity and tenancy -------------------------------------------------------

CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL,
  display_name text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
  data_residency_policy text NOT NULL DEFAULT 'MA_ONLY'
    CHECK (data_residency_policy IN ('MA_ONLY','EU_ALLOWED','GLOBAL_ALLOWED')),
  cndp_declaration_ref text,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_subject text NOT NULL UNIQUE,
  email citext NOT NULL UNIQUE,
  full_name text NOT NULL,
  locale text NOT NULL DEFAULT 'fr-MA' CHECK (locale IN ('fr-MA','ar-MA','en')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','disabled')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('owner','manager','accountant','staff','client_user','operator')),
  professional_title text CHECK (professional_title IN ('expert_comptable','comptable_agree')),
  professional_registration_no text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','revoked')),
  operator_access_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id),
  CHECK ((professional_title IS NULL) = (professional_registration_no IS NULL)),
  CHECK (role <> 'operator' OR operator_access_expires_at IS NOT NULL)
);

CREATE OR REPLACE FUNCTION app.resolve_membership(p_subject text)
RETURNS TABLE(tenant_id uuid, membership_id uuid, role text, client_scope_ids uuid[])
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.tenant_id,
    m.id AS membership_id,
    m.role,
    COALESCE(array_agg(s.client_entity_id) FILTER (WHERE s.client_entity_id IS NOT NULL), '{}'::uuid[]) AS client_scope_ids
  FROM users u
  JOIN memberships m ON m.user_id = u.id AND m.status = 'active'
  JOIN tenants t ON t.id = m.tenant_id AND t.status = 'active'
  LEFT JOIN membership_client_scopes s ON s.membership_id = m.id AND s.tenant_id = m.tenant_id
  WHERE u.identity_subject = p_subject AND u.status = 'active'
  GROUP BY m.tenant_id, m.id, m.role;
END $$;

-- Client companies, periods, chart -------------------------------------------

CREATE TABLE client_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  legal_name text NOT NULL,
  display_name text,
  ice char(15) CHECK (ice ~ '^[0-9]{15}$'),
  if_number text CHECK (if_number ~ '^[0-9]{1,10}$'),
  rc_number text,
  rc_city text,
  tp_number text,
  legal_form text,
  vat_regime text NOT NULL DEFAULT 'encaissement' CHECK (vat_regime IN ('encaissement','debit','not_liable')),
  vat_filing_frequency text NOT NULL DEFAULT 'quarterly' CHECK (vat_filing_frequency IN ('monthly','quarterly')),
  vat_prorata numeric(5,4) CHECK (vat_prorata BETWEEN 0 AND 1),
  is_auto_entrepreneur boolean NOT NULL DEFAULT false,
  functional_currency char(3) NOT NULL DEFAULT 'MAD' CHECK (functional_currency = 'MAD'),
  export_profile_id uuid,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, ice)
);

CREATE TABLE membership_client_scopes (
  tenant_id uuid NOT NULL,
  membership_id uuid NOT NULL REFERENCES memberships(id),
  client_entity_id uuid NOT NULL,
  PRIMARY KEY (tenant_id, membership_id, client_entity_id),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id)
);

CREATE TABLE accounting_periods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  period_code text NOT NULL CHECK (period_code ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  starts_on date NOT NULL,
  ends_on date NOT NULL,
  fiscal_year_end date NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_review','approved','closed')),
  jurisdiction_pack_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, period_code),
  CHECK (ends_on >= starts_on),
  EXCLUDE USING gist (
    tenant_id WITH =, client_entity_id WITH =,
    daterange(starts_on, ends_on, '[]') WITH &&)
);

CREATE TABLE chart_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  account_code text NOT NULL CHECK (account_code ~ '^[0-8][0-9]{3,}$'),
  external_code text,
  label text NOT NULL,
  cgnc_class smallint GENERATED ALWAYS AS (substr(account_code,1,1)::smallint) STORED,
  is_auxiliary_parent boolean NOT NULL DEFAULT false,
  effective_from date NOT NULL DEFAULT '1900-01-01',
  effective_to date,
  source text NOT NULL DEFAULT 'firm_import' CHECK (source IN ('firm_import','cgnc_seed','manual')),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  EXCLUDE USING gist (
    tenant_id WITH =, client_entity_id WITH =, account_code WITH =,
    daterange(effective_from, effective_to, '[)') WITH &&)
);

-- Global, non-tenant: jurisdiction pack tax codes (loaded from YAML, read-only to app)
CREATE TABLE jurisdiction_tax_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pack_code text NOT NULL DEFAULT 'MA',
  pack_version text NOT NULL,
  code text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('vat_rate','vat_exempt_with_credit','vat_exempt_no_credit','out_of_scope','withholding')),
  rate numeric(7,4),
  effective_from date NOT NULL,
  effective_to date,
  source_ref text NOT NULL,
  status text NOT NULL CHECK (status IN ('verified','needs_expert')),
  UNIQUE (pack_code, pack_version, code, effective_from)
);

CREATE TABLE client_tax_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  tax_code text NOT NULL,
  direction text NOT NULL CHECK (direction IN ('purchase','sale','fixed_asset','withholding')),
  account_id uuid NOT NULL,
  approved_by uuid REFERENCES users(id),
  approved_at timestamptz,
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, account_id) REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, tax_code, direction)
);

CREATE TABLE counterparties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('supplier','customer','both','bank','state')),
  legal_name text NOT NULL,
  ice char(15) CHECK (ice ~ '^[0-9]{15}$'),
  if_number text,
  rc_number text,
  is_auto_entrepreneur boolean NOT NULL DEFAULT false,
  tax_compliance_certificate_valid_until date,
  default_account_id uuid,
  auxiliary_code text,
  verified_at timestamptz,
  verification_source text,
  aliases text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, default_account_id) REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE NULLS NOT DISTINCT (tenant_id, client_entity_id, ice, legal_name)
);

-- Work --------------------------------------------------------------------------

CREATE TABLE work_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  accounting_period_id uuid NOT NULL,
  service_code text NOT NULL CHECK (service_code = 'monthly_bookkeeping'),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft','intake','extracting','preparing','reconciling','quality_check',
    'needs_attention','awaiting_approval','exporting','completed',
    'completed_with_open_items','cancelled','failed')),
  current_revision integer NOT NULL DEFAULT 1,
  assigned_to uuid REFERENCES users(id),
  requested_by uuid REFERENCES users(id),
  due_at timestamptz,
  submitted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, accounting_period_id)
    REFERENCES accounting_periods(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE UNIQUE INDEX work_requests_one_active_per_period
  ON work_requests (tenant_id, accounting_period_id)
  WHERE status NOT IN ('cancelled','failed');
CREATE INDEX work_requests_queue ON work_requests (tenant_id, status, due_at);

-- Documents ----------------------------------------------------------------------

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid,
  doc_type text CHECK (doc_type IN (
    'purchase_invoice','sales_invoice','credit_note','receipt','bank_statement',
    'expense_note','customs_document','other')),
  status text NOT NULL DEFAULT 'received' CHECK (status IN (
    'received','quarantined','processing','read','needs_review','rejected')),
  original_filename text NOT NULL,
  source_channel text NOT NULL CHECK (source_channel IN ('console','portal','email','api')),
  uploaded_by uuid REFERENCES users(id),
  fiscal_year_end date,
  retain_until date,
  legal_hold boolean NOT NULL DEFAULT false,
  received_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE INDEX documents_by_work ON documents (tenant_id, work_request_id);

CREATE TABLE document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  document_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  object_key text NOT NULL,
  sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  mime_type text NOT NULL CHECK (mime_type IN (
    'application/pdf','image/jpeg','image/png','image/heic','image/tiff',
    'text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/xml')),
  byte_size bigint NOT NULL CHECK (byte_size > 0 AND byte_size <= 52428800),
  page_count integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, document_id, version_number),
  UNIQUE (tenant_id, client_entity_id, sha256),
  UNIQUE (tenant_id, id)
);

CREATE TABLE extractions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  schema_version text NOT NULL,
  engine text NOT NULL,
  engine_version text NOT NULL,
  provider_call_id uuid,
  status text NOT NULL CHECK (status IN ('succeeded','partial','failed')),
  fields jsonb NOT NULL,
  validation jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, document_version_id) REFERENCES document_versions(tenant_id, id),
  UNIQUE (tenant_id, id)
);

-- Accounting proposals ------------------------------------------------------------

CREATE TABLE journal_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  revision integer NOT NULL,
  journal_code text NOT NULL CHECK (journal_code ~ '^[A-Z0-9]{2,6}$'),
  entry_date date NOT NULL,
  label text NOT NULL,
  source_document_id uuid,
  source_bank_transaction_id uuid,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN (
    'proposed','edited','approved','exported','superseded','rejected')),
  supersedes_id uuid,
  reversal_of_id uuid,
  rule_refs text[] NOT NULL DEFAULT '{}',
  proposed_by text NOT NULL CHECK (proposed_by IN ('rules','agent','human')),
  agent_run_id uuid,
  last_edited_by uuid REFERENCES users(id),
  content_hash char(64),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, source_document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id)
);
CREATE INDEX journal_proposals_by_work ON journal_proposals (tenant_id, work_request_id, revision);

CREATE TABLE journal_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  journal_proposal_id uuid NOT NULL,
  line_no integer NOT NULL CHECK (line_no > 0),
  account_id uuid NOT NULL,
  account_code text NOT NULL,
  counterparty_id uuid,
  label text NOT NULL,
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  debit_tx numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit_tx >= 0),
  credit_tx numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit_tx >= 0),
  fx_rate numeric(18,8) NOT NULL DEFAULT 1 CHECK (fx_rate > 0),
  fx_rate_date date,
  fx_source text,
  debit_mad numeric(18,2) NOT NULL DEFAULT 0 CHECK (debit_mad >= 0),
  credit_mad numeric(18,2) NOT NULL DEFAULT 0 CHECK (credit_mad >= 0),
  tax_code text,
  due_date date,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  FOREIGN KEY (tenant_id, client_entity_id, journal_proposal_id)
    REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, account_id)
    REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, counterparty_id)
    REFERENCES counterparties(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, journal_proposal_id, line_no),
  CHECK ((debit_mad > 0) <> (credit_mad > 0)),
  CHECK ((debit_tx > 0) <> (credit_tx > 0)),
  CHECK ((debit_tx > 0) = (debit_mad > 0)),
  CHECK (currency = 'MAD' OR (fx_rate_date IS NOT NULL AND fx_source IS NOT NULL)),
  CHECK (currency <> 'MAD' OR fx_rate = 1)
);

CREATE OR REPLACE FUNCTION app.assert_proposal_balanced() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_tenant uuid := coalesce(NEW.tenant_id, OLD.tenant_id);
  v_prop   uuid := coalesce(NEW.journal_proposal_id, OLD.journal_proposal_id);
  v_d numeric; v_c numeric; v_n int;
BEGIN
  SELECT coalesce(sum(debit_mad),0), coalesce(sum(credit_mad),0), count(*)
    INTO v_d, v_c, v_n
    FROM journal_lines WHERE tenant_id = v_tenant AND journal_proposal_id = v_prop;
  IF v_n = 0 THEN
    RAISE EXCEPTION 'proposal % has no lines', v_prop USING ERRCODE = '23514';
  END IF;
  IF v_n < 2 OR v_d <> v_c THEN
    RAISE EXCEPTION 'proposal % unbalanced: lines=%, debit=%, credit=%', v_prop, v_n, v_d, v_c
      USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER journal_lines_balanced
  AFTER INSERT OR UPDATE OR DELETE ON journal_lines
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION app.assert_proposal_balanced();

CREATE OR REPLACE FUNCTION app.forbid_frozen_line_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_status text;
BEGIN
  SELECT status INTO v_status FROM journal_proposals
   WHERE tenant_id = coalesce(NEW.tenant_id, OLD.tenant_id)
     AND id = coalesce(NEW.journal_proposal_id, OLD.journal_proposal_id);
  IF v_status IN ('approved','exported','superseded') THEN
    RAISE EXCEPTION 'lines of a % proposal are immutable', v_status USING ERRCODE = '42501';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.journal_proposal_id <> OLD.journal_proposal_id THEN
    RAISE EXCEPTION 'cannot move a line to another proposal' USING ERRCODE = '42501';
  END IF;
  RETURN coalesce(NEW, OLD);
END $$;

CREATE TRIGGER journal_lines_frozen
  BEFORE UPDATE OR DELETE ON journal_lines
  FOR EACH ROW EXECUTE FUNCTION app.forbid_frozen_line_change();

-- Bank ---------------------------------------------------------------------------

CREATE TABLE bank_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_code char(3) NOT NULL,
  rib_last4 char(4) NOT NULL,
  rib_encrypted bytea NOT NULL,
  rib_sha256 char(64) NOT NULL,
  currency char(3) NOT NULL DEFAULT 'MAD',
  ledger_account_id uuid NOT NULL,
  journal_code text NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id) REFERENCES client_entities(tenant_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, ledger_account_id)
    REFERENCES chart_accounts(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, rib_sha256)
);

CREATE TABLE bank_statements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_account_id uuid NOT NULL,
  document_id uuid NOT NULL,
  period_start date NOT NULL,
  period_end date NOT NULL,
  opening_balance numeric(18,2) NOT NULL,
  closing_balance numeric(18,2) NOT NULL,
  balance_check text NOT NULL CHECK (balance_check IN ('ok','break','unknown')),
  FOREIGN KEY (tenant_id, client_entity_id, bank_account_id)
    REFERENCES bank_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, document_id)
    REFERENCES documents(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id)
);

CREATE TABLE bank_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  bank_account_id uuid NOT NULL,
  bank_statement_id uuid NOT NULL,
  line_index integer NOT NULL,
  booking_date date NOT NULL,
  value_date date,
  amount numeric(18,2) NOT NULL CHECK (amount <> 0),
  currency char(3) NOT NULL,
  description text NOT NULL,
  external_reference text,
  source_hash char(64) NOT NULL,
  evidence_ref jsonb NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id, bank_account_id)
    REFERENCES bank_accounts(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, bank_statement_id)
    REFERENCES bank_statements(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, bank_account_id, source_hash)
);
CREATE UNIQUE INDEX bank_tx_ext_ref ON bank_transactions (tenant_id, bank_account_id, external_reference)
  WHERE external_reference IS NOT NULL;

ALTER TABLE journal_proposals
  ADD FOREIGN KEY (tenant_id, client_entity_id, source_bank_transaction_id)
  REFERENCES bank_transactions(tenant_id, client_entity_id, id);

CREATE TABLE reconciliation_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected','superseded')),
  score numeric(5,4) CHECK (score BETWEEN 0 AND 1),
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  difference_mad numeric(18,2) NOT NULL DEFAULT 0,
  difference_kind text CHECK (difference_kind IN ('vat_withheld','bank_fee','fx','rounding','unexplained')),
  decided_by uuid REFERENCES users(id),
  decided_at timestamptz,
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id)
    REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, client_entity_id, id)
);

CREATE TABLE reconciliation_match_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  match_id uuid NOT NULL,
  bank_transaction_id uuid,
  journal_proposal_id uuid,
  document_id uuid,
  amount_mad numeric(18,2) NOT NULL,
  FOREIGN KEY (tenant_id, client_entity_id, match_id) REFERENCES reconciliation_matches(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, bank_transaction_id) REFERENCES bank_transactions(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, journal_proposal_id) REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, document_id) REFERENCES documents(tenant_id, client_entity_id, id),
  CHECK (num_nonnulls(bank_transaction_id, journal_proposal_id, document_id) = 1)
);
CREATE UNIQUE INDEX one_accepted_match_per_bank_line
  ON reconciliation_match_items (tenant_id, bank_transaction_id)
  WHERE bank_transaction_id IS NOT NULL;

-- Issues, approvals, exports -------------------------------------------------------

CREATE TABLE issues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('blocking','review','info')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','assigned','waiting_client','resolved','waived')),
  resolution text CHECK (resolution IN ('fixed','accepted_as_is','waived','sent_to_client')),
  resolution_note text,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  subject_document_id uuid,
  subject_proposal_id uuid,
  subject_bank_transaction_id uuid,
  assigned_to uuid REFERENCES users(id),
  resolved_by uuid REFERENCES users(id),
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_document_id) REFERENCES documents(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_proposal_id) REFERENCES journal_proposals(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, client_entity_id, subject_bank_transaction_id) REFERENCES bank_transactions(tenant_id, client_entity_id, id),
  CHECK ((status IN ('resolved','waived')) = (resolved_at IS NOT NULL)),
  CHECK (NOT (severity = 'blocking' AND resolution = 'accepted_as_is'))
);
CREATE INDEX issues_open ON issues (tenant_id, work_request_id) WHERE status NOT IN ('resolved','waived');

CREATE TABLE approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  revision integer NOT NULL,
  subject_hash char(64) NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled')),
  prepared_by uuid REFERENCES users(id),
  decided_by uuid REFERENCES users(id),
  decider_professional_title text,
  decider_registration_no text,
  single_person_policy boolean NOT NULL DEFAULT false,
  reason text,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, id),
  CHECK (status = 'pending' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL AND reason IS NOT NULL)),
  CHECK (status <> 'approved' OR decider_registration_no IS NOT NULL),
  CHECK (single_person_policy OR decided_by IS NULL OR prepared_by IS NULL OR decided_by <> prepared_by)
);

CREATE TABLE export_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text NOT NULL,
  target text NOT NULL CHECK (target IN ('sage100_csv','sage100_pnm','odoo_csv')),
  encoding text NOT NULL DEFAULT 'cp1252' CHECK (encoding IN ('cp1252','utf-8')),
  config jsonb NOT NULL,
  verified_round_trip_at timestamptz,
  UNIQUE (tenant_id, id)
);

CREATE TABLE exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  approval_id uuid NOT NULL,
  export_profile_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'preparing' CHECK (status IN ('preparing','ready','downloaded','failed')),
  object_key text,
  file_sha256 char(64),
  evidence_pack_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  FOREIGN KEY (tenant_id, approval_id) REFERENCES approvals(tenant_id, id),
  FOREIGN KEY (tenant_id, export_profile_id) REFERENCES export_profiles(tenant_id, id)
);

-- Operations ---------------------------------------------------------------------

CREATE TABLE provider_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  provider text NOT NULL,
  region text NOT NULL,
  model text,
  purpose text NOT NULL,
  input_sha256 char(64) NOT NULL,
  usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  cost_mad numeric(18,6),
  status text NOT NULL CHECK (status IN ('succeeded','failed','refused_by_policy')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  task text NOT NULL,
  agent_version text NOT NULL,
  prompt_version text NOT NULL,
  input_refs jsonb NOT NULL,
  output jsonb,
  schema_valid boolean NOT NULL,
  provider_call_id uuid REFERENCES provider_calls(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id)
);

CREATE TABLE idempotency_keys (
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  key text NOT NULL CHECK (length(key) BETWEEN 8 AND 200),
  method text NOT NULL,
  path text NOT NULL,
  request_sha256 char(64) NOT NULL,
  status text NOT NULL CHECK (status IN ('in_progress','completed')),
  response_code integer,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);

CREATE TABLE usage_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  client_entity_id uuid NOT NULL,
  work_request_id uuid NOT NULL,
  unit text NOT NULL CHECK (unit IN ('monthly_file','extra_document','client_request')),
  quantity numeric(18,4) NOT NULL CHECK (quantity > 0),
  price_version text NOT NULL,
  billable boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_entity_id, work_request_id) REFERENCES work_requests(tenant_id, client_entity_id, id),
  UNIQUE (tenant_id, work_request_id, unit)
);

CREATE TABLE evidence_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  subject_type text NOT NULL CHECK (subject_type IN ('document','extraction','proposal','line','match','issue','approval','export')),
  subject_id uuid NOT NULL,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  content_sha256 char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id)
);

CREATE TABLE audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  actor_type text NOT NULL CHECK (actor_type IN ('user','system','agent','operator')),
  actor_id text,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id text,
  request_id text,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  prev_hash char(64),
  row_hash char(64) NOT NULL
);
CREATE INDEX audit_events_tenant_time ON audit_events (tenant_id, occurred_at DESC);

-- updated_at triggers
CREATE TRIGGER t_tenants_touch BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_users_touch BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_clients_touch BEFORE UPDATE ON client_entities FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
CREATE TRIGGER t_work_touch BEFORE UPDATE ON work_requests FOR EACH ROW EXECUTE FUNCTION app.touch_updated_at();
