// Report builder — assembles the production-grade pre-check report structure.
// The report is generated in the current UI locale (section titles and static
// phrases via t()); dynamic data (scores, extracted values, audit details)
// is preserved as stored.

import type { AnalysisResult, Dossier, Organization, Report, ReportSection } from '@/types/models';
import { generateId } from './id';
import { t } from '@/i18n';

export const REQUIRED_REPORT_SECTIONS = [
  'executive_summary',
  'extracted_data',
  'fiscal_findings',
  'customs_findings',
  'missing_documents',
  'anomalies',
  'recommended_actions',
  'expert_review',
  'audit_trail',
  'disclaimer',
] as const;

export function buildReport(
  organization: Organization,
  dossier: Dossier,
  analysis: AnalysisResult,
  expertReviewStatus: Report['expertReviewStatus'],
  auditSummary: string,
): Report {
  const { scores } = analysis;
  const fiscalFindings = scores.findings.filter((f) => f.domain === 'fiscal');
  const customsFindings = scores.findings.filter((f) => f.domain === 'customs');
  const missingDocs = analysis.checklist.filter((c) => c.status === 'missing');
  const anomalies = scores.findings.filter(
    (f) => f.severity === 'critical' || f.severity === 'high',
  );
  const disclaimer = t('legal.disclaimer');

  const sections: ReportSection[] = [
    {
      key: 'executive_summary',
      title: t('report.section.executive_summary'),
      content: t('report.summary', {
        title: dossier.title,
        type: t(`dossierType.${dossier.type}`),
        client: dossier.clientName,
        overall: scores.overall,
        level: t(`risk.${scores.level}`),
        fiscal: scores.fiscal,
        customs: scores.customs,
        findings: scores.findings.length,
        reviewSentence: scores.expertReviewRequired
          ? t('report.summary.reviewRequired')
          : t('report.summary.reviewOptional'),
      }),
    },
    {
      key: 'extracted_data',
      title: t('report.section.extracted_data'),
      content:
        analysis.extractions.length === 0
          ? t('report.extracted.none')
          : analysis.extractions
              .map((e) =>
                t('report.extracted.line', {
                  type: t(`docType.${e.documentType}`),
                  confidence: (e.confidence * 100).toFixed(0),
                  fields: e.fields.map((f) => `${f.label}: ${f.value ?? '—'}`).join(' · '),
                }),
              )
              .join('\n'),
    },
    {
      key: 'fiscal_findings',
      title: t('report.section.fiscal_findings'),
      content:
        fiscalFindings.length === 0
          ? t('report.fiscal.none')
          : fiscalFindings.map((f) => `• ${f.title} — ${f.detail}`).join('\n'),
    },
    {
      key: 'customs_findings',
      title: t('report.section.customs_findings'),
      content:
        customsFindings.length === 0
          ? t('report.customs.none')
          : customsFindings.map((f) => `• ${f.title} — ${f.detail}`).join('\n'),
    },
    {
      key: 'missing_documents',
      title: t('report.section.missing_documents'),
      content:
        missingDocs.length === 0
          ? t('report.missing.none')
          : missingDocs.map((d) => `• ${d.label}`).join('\n'),
    },
    {
      key: 'anomalies',
      title: t('report.section.anomalies'),
      content:
        anomalies.length === 0
          ? t('report.anomalies.none')
          : anomalies.map((f) => `• [${t(`severity.${f.severity}`)}] ${f.title}`).join('\n'),
    },
    {
      key: 'recommended_actions',
      title: t('report.section.recommended_actions'),
      content:
        scores.findings.length === 0
          ? t('report.actions.ready')
          : scores.findings.map((f) => `• ${f.recommendedAction}`).join('\n'),
    },
    {
      key: 'expert_review',
      title: t('report.section.expert_review'),
      content:
        expertReviewStatus === 'validated'
          ? t('report.expert.validated')
          : expertReviewStatus === 'correction_required'
            ? t('report.expert.correction')
            : expertReviewStatus === 'pending'
              ? t('report.expert.pending')
              : t('report.expert.notRequired'),
    },
    { key: 'audit_trail', title: t('report.section.audit_trail'), content: auditSummary },
    { key: 'disclaimer', title: t('report.section.disclaimer'), content: disclaimer },
  ];

  return {
    id: generateId('rpt'),
    organizationId: organization.id,
    organizationName: organization.name,
    dossierId: dossier.id,
    dossierTitle: dossier.title,
    clientName: dossier.clientName,
    date: new Date().toISOString(),
    scores,
    sections,
    expertReviewStatus,
    disclaimer,
  };
}
