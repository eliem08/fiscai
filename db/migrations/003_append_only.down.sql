-- 003_append_only.down.sql (run as avenel_owner)

DROP TRIGGER IF EXISTS audit_chain ON audit_events;
DROP FUNCTION IF EXISTS app.chain_audit() CASCADE;

DROP VIEW IF EXISTS document_versions_current CASCADE;

DROP TRIGGER IF EXISTS extraction_no_mutation ON extractions;
DROP TRIGGER IF EXISTS docver_no_mutation ON document_versions;
DROP TRIGGER IF EXISTS evidence_no_mutation ON evidence_records;
DROP TRIGGER IF EXISTS audit_no_mutation ON audit_events;

DROP FUNCTION IF EXISTS app.forbid_mutation() CASCADE;
