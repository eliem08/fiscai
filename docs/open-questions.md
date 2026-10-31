# AVENEL Open Questions

This file records questions, ambiguities, and chosen restrictive interpretations according to Rule A.3:
*"When the spec is ambiguous, choose the more restrictive interpretation (deny access, require review, block export) and record the question in `docs/open-questions.md`."*

---

## 1. Malware Scan Tracking on Append-Only `document_versions`
- **Context**: In `ARCHITECTURE.md` D.3, `001_core.sql` defines `document_versions.malware_scan`, but `003_append_only.sql` forbids any `UPDATE` or `DELETE` on `document_versions` (`docver_no_mutation`). Lines 958 & 983 note: *"malware_scan result is recorded as a new evidence row, not by updating document_versions. Remove the malware_scan column from document_versions if you implement it this way; do not leave two sources of truth."*
- **Restrictive Choice**: To strictly preserve the immutability invariant (Invariant 6 & Rule A.2 #5), malware scans are appended as `evidence_records` (`kind = 'malware_scan'`). A view `document_versions_current` exposes the latest scan status without updating `document_versions`. Any document without a verified clean scan in evidence remains quarantined/unprocessed.
- **Status**: Recorded, restrictive policy applied.

---

## 2. Pre-Tenant Membership Resolution Function
- **Context**: `ARCHITECTURE.md` D.3 (line 940) specifies: *"Membership resolution happens before tenant context exists. It runs through a `SECURITY DEFINER` function `app.resolve_membership(subject text)` owned by `avenel_owner`, returning only `(tenant_id, membership_id, role, client_scope_ids)` for that subject. No other cross-tenant read path exists."*
- **Restrictive Choice**: The function is owned by `avenel_owner` and returns only active memberships for active users and active tenants, with exact client scope IDs. If a user or tenant is disabled or suspended, the function returns an empty set.
- **Status**: Specified in migration 001/002.

---

## 3. Basis of Cash Payment Limits (HT vs TTC) under CGI Art. 106-II
- **Context**: Item 1 of Part I. Rule in `vat_deduction.yaml`.
- **Restrictive Choice**: Apply TTC basis (more conservative, triggers limit sooner), and tag rule with `status: needs_expert`.
- **Status**: Tagged in jurisdiction pack.

---

## 4. ICE Check-Digit Algorithm
- **Context**: Item 5 of Part I. ICE is 15 digits; check-digit validation formula is not legally standardized.
- **Restrictive Choice**: Format regex `^[0-9]{15}$` is strictly enforced; check digit mismatch is surfaced as a warning only (`status: needs_expert`).
- **Status**: Tagged in jurisdiction pack.

---

## 5. MinIO Licensing (AGPLv3) and Patch Maintenance Policy
- **Context**: In `docker-compose.yml`, local S3 object storage is provided by MinIO (`RELEASE.2024-10-13T13-34-11Z`). MinIO community releases are licensed under the GNU Affero General Public License v3 (AGPLv3). In multi-tenant SaaS platforms, AGPLv3 raises legal compliance concerns regarding copyleft obligations over network interactions if proprietary code is coupled or linked with MinIO internals. Additionally, MinIO upstream does not offer backported security patches for older community releases, requiring immediate forward migration for any vulnerability remediation.
- **Restrictive Choice**:
  1. **Strict Architectural Isolation**: MinIO is strictly confined to local development and ephemeral test environments. All application interactions must occur exclusively over the public S3 REST API protocol using standard, vendor-neutral S3 clients (`boto3`, `@aws-sdk/client-s3`), with zero MinIO-specific SDKs or runtime coupling.
  2. **Production Cloud Target**: Production deployments of AVENEL shall NOT self-host community MinIO. Production environments mandate managed S3-compliant object storage services (AWS S3 or Cloudflare R2) or an enterprise-licensed cluster (MinIO Enterprise or Ceph S3) to eliminate AGPLv3 copyleft risk and ensure vendor security patch SLAs.
- **Status**: Architectural boundary enforced; production target pinned to managed S3/R2.

