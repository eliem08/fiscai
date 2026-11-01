-- 008_round_trips_and_approval_policy.up.sql
-- Phase 5 additions:
-- 1. Client entities single_person_policy flag
-- 2. Export round-trip audit logging table with forced RLS
-- 3. Approvals decider professional title domain check constraint

ALTER TABLE client_entities ADD COLUMN IF NOT EXISTS single_person_policy boolean NOT NULL DEFAULT false;

CREATE TABLE export_round_trips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  export_profile_id uuid NOT NULL,
  software text NOT NULL,
  version text NOT NULL,
  imported_at timestamptz NOT NULL,
  result text NOT NULL CHECK (result IN ('ok', 'failed')),
  notes text,
  screenshot_document_id uuid REFERENCES documents(id),
  recorded_by uuid NOT NULL REFERENCES users(id),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, export_profile_id) REFERENCES export_profiles(tenant_id, id)
);

ALTER TABLE export_round_trips ENABLE ROW LEVEL SECURITY;
ALTER TABLE export_round_trips FORCE ROW LEVEL SECURITY;
CREATE POLICY export_round_trips_tenant_isolation ON export_round_trips
  USING (tenant_id = app.current_tenant());

ALTER TABLE approvals ADD CONSTRAINT approvals_decider_title_check
  CHECK (decider_professional_title IS NULL OR decider_professional_title IN ('expert_comptable', 'comptable_agree'));

