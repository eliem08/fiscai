-- 008_round_trips_and_approval_policy.down.sql
-- Rollback Phase 5 round trips and approval policy additions

ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_decider_title_check;
DROP TABLE IF EXISTS export_round_trips CASCADE;
ALTER TABLE client_entities DROP COLUMN IF EXISTS single_person_policy;

