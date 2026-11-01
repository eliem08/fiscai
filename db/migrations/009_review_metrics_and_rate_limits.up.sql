-- 009_review_metrics_and_rate_limits.up.sql
-- Review-effort metrics & shared-store rate limiter

-- 1. Review effort metrics per user per monthly file
CREATE TABLE review_effort_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  work_request_id uuid NOT NULL,
  user_id uuid NOT NULL REFERENCES users(id),
  active_review_seconds integer NOT NULL DEFAULT 0,
  fields_corrected integer NOT NULL DEFAULT 0,
  entries_edited integer NOT NULL DEFAULT 0,
  issues_resolved integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, work_request_id) REFERENCES work_requests(tenant_id, id),
  UNIQUE (tenant_id, work_request_id, user_id)
);

ALTER TABLE review_effort_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_effort_metrics FORCE ROW LEVEL SECURITY;
CREATE POLICY review_effort_metrics_tenant_isolation ON review_effort_metrics
  USING (tenant_id = app.current_tenant())
  WITH CHECK (tenant_id = app.current_tenant());

-- 2. Shared-store rate limit buckets (multi-worker synchronization)
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
  bucket_key text PRIMARY KEY,
  tokens double precision NOT NULL,
  last_refilled_at double precision NOT NULL
);

GRANT SELECT, INSERT, UPDATE, DELETE ON review_effort_metrics, rate_limit_buckets TO avenel_app;

