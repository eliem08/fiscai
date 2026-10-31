-- 003_append_only.up.sql (run as avenel_owner)

CREATE OR REPLACE FUNCTION app.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '42501';
END $$;

DROP TRIGGER IF EXISTS audit_no_mutation ON audit_events;
CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS evidence_no_mutation ON evidence_records;
CREATE TRIGGER evidence_no_mutation BEFORE UPDATE OR DELETE ON evidence_records
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS docver_no_mutation ON document_versions;
CREATE TRIGGER docver_no_mutation BEFORE UPDATE OR DELETE ON document_versions
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS extraction_no_mutation ON extractions;
CREATE TRIGGER extraction_no_mutation BEFORE UPDATE OR DELETE ON extractions
  FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- malware_scan result is recorded as a new evidence row, not by updating document_versions.
CREATE OR REPLACE VIEW document_versions_current AS
SELECT
  dv.*,
  COALESCE(
    (
      SELECT er.payload->>'status'
      FROM evidence_records er
      WHERE er.tenant_id = dv.tenant_id
        AND er.subject_type = 'document'
        AND er.subject_id = dv.document_id
        AND er.kind = 'malware_scan'
      ORDER BY er.created_at DESC
      LIMIT 1
    ),
    'pending'
  ) AS malware_scan_status
FROM document_versions dv;

REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, evidence_records, document_versions, extractions FROM avenel_app;
GRANT SELECT ON document_versions_current TO avenel_app;

CREATE OR REPLACE FUNCTION app.chain_audit() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_prev char(64);
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.tenant_id::text, 0));
  SELECT row_hash INTO v_prev FROM audit_events
   WHERE tenant_id = NEW.tenant_id ORDER BY id DESC LIMIT 1;
  NEW.prev_hash := v_prev;
  NEW.row_hash := encode(digest(
    coalesce(v_prev,'') || NEW.tenant_id::text || NEW.actor_type || coalesce(NEW.actor_id,'') ||
    NEW.action || NEW.resource_type || coalesce(NEW.resource_id,'') ||
    NEW.data::text || NEW.occurred_at::text, 'sha256'), 'hex');
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS audit_chain ON audit_events;
CREATE TRIGGER audit_chain BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION app.chain_audit();
