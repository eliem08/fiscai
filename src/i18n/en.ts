import type { fr } from './fr';

// English catalog. Must have exactly the same keys as the French reference
// (enforced by the TranslationCatalog type and the parity test).
export const en: Record<keyof typeof fr, string> = {
  // --- Common ---
  'common.appName': 'FiscAI PreClear',
  'common.cancel': 'Cancel',
  'common.save': 'Save',
  'common.saving': 'Saving…',
  'common.retry': 'Retry',
  'common.loading': 'Loading…',
  'common.loadingPage': 'Loading page…',
  'common.search': 'Search',
  'common.all': 'All',
  'common.allF': 'All',
  'common.status': 'Status',
  'common.type': 'Type',
  'common.severity': 'Severity',
  'common.actionLabel': 'Action',
  'common.recommendedAction': 'Recommended action',
  'common.close': 'Close',
  'common.open': 'Open',
  'common.backHome': '← Back to home',
  'common.optional': 'optional',
  'common.of100': '/100',

  // --- Disclaimer / privacy ---
  'legal.disclaimer':
    'FiscAI provides fiscal and customs pre-check assistance. Results must be verified by an accountant, a customs broker or an authorized expert before any official use.',
  'legal.privacy':
    'Your documents are handled confidentially and are never shared with third parties without your consent. FiscAI is a decision-support tool: no official fiscal or customs decision is made without human review.',
  'legal.disclaimerPrefix': 'Disclaimer: ',
  'legal.readOnly': 'Read-only mode enabled to protect your data.',

  // --- Navigation ---
  'nav.dashboard': 'Dashboard',
  'nav.dossiers': 'Dossiers',
  'nav.documents': 'Documents',
  'nav.agents': 'AI Agents',
  'nav.alerts': 'Alerts',
  'nav.expertReview': 'Expert review',
  'nav.reports': 'Reports',
  'nav.audit': 'Audit log',
  'nav.settings': 'Settings',
  'nav.pricing': 'Pricing',
  'nav.login': 'Sign in',
  'nav.logout': 'Sign out',
  'nav.sidebarNote': 'AI pre-check — results require expert validation.',
  'nav.mainNav': 'Main navigation',
  'nav.publicNav': 'Public navigation',
  'nav.workspace': 'Workspace',

  // --- Roles / language ---
  'role.admin': 'admin',
  'role.analyst': 'analyst',
  'role.expert': 'expert',
  'role.viewer': 'viewer',
  'lang.label': 'Interface language',
  'lang.fr': 'Français',
  'lang.en': 'English',

  // --- Risk levels ---
  'risk.low': 'Low risk',
  'risk.medium': 'Medium risk',
  'risk.high': 'High risk',
  'risk.critical': 'Critical risk',
  'risk.scoreAria': 'score {score} out of 100',

  // --- Severity ---
  'severity.label': 'Severity: {value}',
  'severity.critical': 'Critical',
  'severity.high': 'High',
  'severity.medium': 'Medium',
  'severity.low': 'Low',

  // --- Dossier status ---
  'dossierStatus.draft': 'Draft',
  'dossierStatus.analyzing': 'Analyzing',
  'dossierStatus.analyzed': 'Analyzed',
  'dossierStatus.needs_review': 'Review required',
  'dossierStatus.reviewed': 'Expert-reviewed',
  'dossierStatus.issue': 'Active issue',

  // --- Dossier types ---
  'dossierType.import': 'Import dossier',
  'dossierType.export': 'Export dossier',
  'dossierType.fiscal': 'Fiscal / VAT dossier',

  // --- Document types ---
  'docType.commercial_invoice': 'Commercial invoice',
  'docType.packing_list': 'Packing list',
  'docType.transport_document': 'Transport document',
  'docType.certificate_origin': 'Certificate of origin',
  'docType.customs_declaration': 'Customs declaration',
  'docType.vat_declaration': 'VAT declaration',
  'docType.other': 'Other document',

  // --- Alert status ---
  'alertStatus.open': 'Open',
  'alertStatus.in_review': 'In review',
  'alertStatus.resolved': 'Resolved',

  // --- Landing ---
  'landing.badge': 'Tax · VAT · Customs — Morocco',
  'landing.heroTitle': 'Pre-check your fiscal and customs dossiers before they go out',
  'landing.heroSubtitle':
    'FiscAI PreClear analyzes your invoices and import/export dossiers with AI agents, detects missing documents and VAT/customs inconsistencies, and prepares a risk report — before you deal with accountants, customs brokers, DGI, PortNet or BADR.',
  'landing.ctaDemo': 'Try the demo',
  'landing.ctaPricing': 'See pricing',
  'landing.featuresAria': 'Features',
  'landing.f1.title': 'Dossier pre-check',
  'landing.f1.text':
    'Analysis of invoices, fiscal documents and import/export dossiers before transmission to your accountants, customs brokers and PortNet/BADR workflows.',
  'landing.f2.title': 'Specialized AI agents',
  'landing.f2.text':
    'Tax, customs, regulation, compliance and anomaly agents work as a pipeline, with evidence and confidence levels.',
  'landing.f3.title': 'Risk score',
  'landing.f3.text':
    'Fiscal and customs scores 0-100, detection of missing documents and VAT / HS-code inconsistencies.',
  'landing.f4.title': 'Alerts and vigilance',
  'landing.f4.text':
    'Prioritized alerts (critical → low) with status tracking until resolution.',
  'landing.f5.title': 'Expert review',
  'landing.f5.text':
    'No official conclusion without human validation: built-in, logged review workflow.',
  'landing.f6.title': 'Ready-to-share reports',
  'landing.f6.text':
    'Structured reports (summary, findings, actions, audit trail) for your experts and partners.',
  'landing.footer':
    '© 2026 FiscAI PreClear — Decision-support tool. Does not replace accountants, customs brokers, or tax/customs authorities.',

  // --- Auth ---
  'auth.loginTitle': 'Sign in',
  'auth.demoHint': 'Demo account: {email} / {password}',
  'auth.email': 'Email address',
  'auth.emailPro': 'Work email address',
  'auth.password': 'Password',
  'auth.passwordRule': 'Password (8 characters min.)',
  'auth.loginCta': 'Sign in',
  'auth.loggingIn': 'Signing in…',
  'auth.noAccount': 'No account?',
  'auth.createAccount': 'Create an account',
  'auth.registerTitle': 'Create an account',
  'auth.fullName': 'Full name',
  'auth.creating': 'Creating account…',
  'auth.createCta': 'Create my account',
  'auth.alreadyMember': 'Already registered?',

  // --- Dashboard ---
  'dashboard.title': 'Dashboard',
  'dashboard.subtitle': 'Overview of your fiscal and customs pre-checks.',
  'dashboard.newDossier': 'New dossier',
  'dashboard.kpiDossiers': 'Active dossiers',
  'dashboard.kpiDossiersHint': 'All types combined',
  'dashboard.kpiReview': 'Awaiting expert review',
  'dashboard.kpiReviewHint': 'Human validation required',
  'dashboard.kpiAlerts': 'Open alerts',
  'dashboard.kpiAlertsHint': 'Critical → low',
  'dashboard.kpiReports': 'Reports generated',
  'dashboard.kpiReportsHint': 'Ready to share',
  'dashboard.recent': 'Recent dossiers',
  'dashboard.seeAll': 'See all dossiers',
  'dashboard.emptyTitle': 'No dossiers yet',
  'dashboard.emptyDesc': 'Create your first dossier to launch a fiscal or customs pre-check.',
  'dashboard.emptyCta': 'Create a dossier',

  // --- Dossiers list ---
  'dossiers.title': 'Dossiers',
  'dossiers.subtitle': 'Search, filter and track your pre-check dossiers.',
  'dossiers.searchPlaceholder': 'Title or client…',
  'dossiers.sort': 'Sort',
  'dossiers.sortDesc': 'Newest first',
  'dossiers.sortAsc': 'Oldest first',
  'dossiers.emptyTitle': 'No dossier found',
  'dossiers.emptyFiltered': 'No dossier matches your filters.',
  'dossiers.emptyDefault': 'Create your first pre-check dossier.',
  'dossiers.updatedOn': 'Updated on {date}',
  'dossiers.ref': 'Ref. {ref}',
  'dossiers.openAria': 'Open dossier {title}',

  // --- New dossier ---
  'newDossier.title': 'New dossier',
  'newDossier.subtitle': 'Create a dossier, add documents, then launch the AI pre-check analysis.',
  'newDossier.typeLabel': 'Dossier type *',
  'newDossier.titleLabel': 'Dossier title *',
  'newDossier.titlePlaceholder': 'e.g. Import electronic components — Shenzhen',
  'newDossier.clientLabel': 'Client / concerned entity *',
  'newDossier.clientPlaceholder': 'e.g. ElectroMaroc SARL',
  'newDossier.refLabel': 'BADR / PortNet reference (optional)',
  'newDossier.refPlaceholder': 'e.g. BADR-2026-11842',
  'newDossier.descLabel': 'Description (optional)',
  'newDossier.descPlaceholder': 'Context, goods, deadlines…',
  'newDossier.creating': 'Creating…',
  'newDossier.submit': 'Create dossier',
  'newDossier.created': 'Dossier “{title}” created.',

  // --- Dossier detail ---
  'dossier.back': 'Dossiers',
  'dossier.createdOn': 'created on {date}',
  'dossier.documents': 'Documents ({count})',
  'dossier.noDocuments': 'No document. Add at least the commercial invoice.',
  'dossier.deleteDocAria': 'Delete document {name}',
  'dossier.launchAnalysis': 'Launch AI analysis',
  'dossier.analyzing': 'Analyzing…',
  'dossier.analysisStep': 'Step {index}/{total} — {agent}',
  'dossier.results': 'Findings',
  'dossier.checklist': 'Checklist',
  'dossier.questions': 'Supplier questions',
  'dossier.agents': 'Agents',
  'dossier.fiscalScore': 'Fiscal score',
  'dossier.customsScore': 'Customs score',
  'dossier.global': 'Overall',
  'dossier.lowConfidence':
    'Low-confidence result: document quality limits extraction reliability. Human verification is essential.',
  'dossier.partial': 'Partial analysis: some required documents are missing.',
  'dossier.noFindings': 'No anomaly detected. Dossier ready for review.',
  'dossier.noAnalysis': 'No analysis yet. Add your documents then launch the AI analysis.',
  'dossier.noAnalysisRight': 'No analysis yet. Add your documents then launch the AI analysis.',
  'dossier.noQuestions': 'No question to send.',
  'dossier.generateReport': 'Generate report',
  'dossier.generating': 'Generating…',
  'dossier.analysisDone': 'Analysis complete: overall score {score}/100.',
  'dossier.analysisFailed': 'Analysis failed',
  'dossier.docSent': 'Document “{name}” uploaded.',
  'dossier.docDeleted': 'Document “{name}” deleted.',
  'dossier.reportGenerated': 'Report generated.',
  'dossier.loadErrorTitle': 'Unable to load this dossier',
  'dossier.backToDossiers': 'Back to dossiers',
  'dossier.confirmPartialTitle': 'Required documents missing',
  'dossier.confirmPartialBody':
    'The commercial invoice is missing from the dossier. You can launch a partial analysis, but the risk score will be degraded and the result flagged as low-confidence.',
  'dossier.addDocuments': 'Add documents',
  'dossier.launchPartial': 'Launch partial analysis',
  'dossier.deleteDocTitle': 'Delete this document?',
  'dossier.deleteDocBody':
    'The document “{name}” will be removed from the dossier. This action is recorded in the audit trail.',
  'dossier.deleteConfirm': 'Delete permanently',

  // --- Upload ---
  'upload.docType': 'Document type',
  'upload.dropHint': 'Drag and drop a file or',
  'upload.choose': 'Choose a file',
  'upload.sending': 'Uploading…',
  'upload.formats': 'PDF, PNG, JPG, XLSX, XML, DOCX — 10 MB max. Secure, confidential upload.',
  'upload.selectAria': 'Select a document to upload',

  // --- Documents library ---
  'documents.title': 'Document library',
  'documents.subtitle': 'All documents uploaded to your workspace.',
  'documents.searchPlaceholder': 'File name…',
  'documents.emptyTitle': 'No document',
  'documents.emptyDesc': 'Documents uploaded from your dossiers will appear here.',
  'documents.colFile': 'File',
  'documents.colType': 'Type',
  'documents.colSize': 'Size',
  'documents.colUploaded': 'Uploaded on',
  'documents.colDossier': 'Dossier',
  'documents.tableCaption': 'List of the organization documents',

  // --- Agents page ---
  'agents.title': 'AI Agents',
  'agents.subtitle':
    'The FiscAI agentic pipeline: each agent is specialized, logged, and subject to human validation for risky cases.',
  'agents.idleAction': 'Launch an analysis from a dossier to activate this agent.',
  'agents.queryTitle': 'Data Query Agent (preview)',
  'agents.queryPlaceholder': "e.g. SELECT * FROM dossiers WHERE status = 'needs_review'",
  'agents.queryLabel': 'Data query',
  'agents.queryTest': 'Test the query',
  'agents.queryChecking': 'Checking…',
  'agent.confidence': 'Confidence: {value}%',
  'agent.evidence': 'Evidence / sources',
  'agent.status.idle': 'Idle',
  'agent.status.running': 'Running',
  'agent.status.completed': 'Completed',
  'agent.status.failed': 'Failed',
  'agent.status.needs_review': 'Human review required',

  // --- Alerts ---
  'alerts.title': 'Alerts center',
  'alerts.subtitle':
    'Alerts generated by the AI analysis, sorted by severity. Process them until resolution.',
  'alerts.emptyTitle': 'No alert',
  'alerts.emptyDesc': 'No alert matches these filters. Good sign!',
  'alerts.statusLabel': 'Status: {value}',
  'alerts.seeDossier': 'See the dossier',
  'alerts.toReview': 'Move to review',
  'alerts.markResolved': 'Mark resolved',
  'alerts.updated': 'Alert “{title}” updated ({status}).',

  // --- Expert review ---
  'review.title': 'Expert review',
  'review.subtitle':
    'Mandatory human validation of high- or critical-risk dossiers before any official use.',
  'review.awaiting': 'Awaiting ({count})',
  'review.emptyTitle': 'No dossier awaiting review',
  'review.emptyDesc': 'High-risk dossiers will appear here after analysis.',
  'review.recent': 'Recent reviews',
  'review.decision': 'Decision',
  'review.selectPrompt': 'Select a dossier awaiting review to examine the AI findings.',
  'review.findingsCount': '{count} AI finding(s)',
  'review.decisionRequired': 'Decision *',
  'review.validated': 'Dossier validated — compliant for transmission',
  'review.correction': 'Correction required — return to client',
  'review.rejected': 'Rejected — dossier not usable',
  'review.commentLabel': 'Expert comment * (logged)',
  'review.commentPlaceholder': 'Justify your decision for the audit trail…',
  'review.submit': 'Save review',
  'review.saved': 'Review saved for “{title}”.',
  'review.decisionValidated': 'Validated',
  'review.decisionCorrection': 'Correction required',

  // --- Reports ---
  'reports.title': 'Reports',
  'reports.subtitle': 'Generated pre-check reports, ready to share with your experts.',
  'reports.emptyTitle': 'No report generated',
  'reports.emptyDesc': 'Generate a report from a dossier analysis page.',
  'reports.seeDossiers': 'See dossiers',
  'reports.openAria': 'Open report {title}',
  'reports.allReports': 'All reports',
  'reports.export': 'Export (text)',
  'reports.exporting': 'Exporting…',
  'reports.exported': 'Report exported.',
  'reports.notFound': 'Report not found',
  'report.heading': 'Fiscal & customs pre-check report',
  'report.client': 'Client',

  // --- Pricing ---
  'pricing.heroTitle': 'Simple, transparent pricing',
  'pricing.heroSubtitle':
    'Choose the plan that fits your dossier volume. No commitment, cancel anytime.',
  'pricing.recommended': 'Recommended',
  'pricing.perMonth': '/month',
  'pricing.start': 'Get started',
  'pricing.contact': 'Contact us',
  'pricing.starter.name': 'Starter',
  'pricing.starter.desc': 'For SMEs starting with import/export.',
  'pricing.pro.name': 'Pro',
  'pricing.pro.desc': 'For accounting firms and customs brokers.',
  'pricing.enterprise.name': 'Enterprise',
  'pricing.enterprise.price': 'Custom quote',
  'pricing.enterprise.desc': 'For groups, institutions and high volumes.',
  'pricing.starter.f1': '10 dossiers / month',
  'pricing.starter.f2': 'AI fiscal and customs analysis',
  'pricing.starter.f3': 'Alerts and checklist',
  'pricing.starter.f4': 'Pre-check reports',
  'pricing.starter.f5': 'Email support',
  'pricing.pro.f1': '60 dossiers / month',
  'pricing.pro.f2': 'Multi-client and multi-user',
  'pricing.pro.f3': 'Built-in expert review',
  'pricing.pro.f4': 'Full audit log',
  'pricing.pro.f5': 'Priority support',
  'pricing.enterprise.f1': 'Unlimited dossiers',
  'pricing.enterprise.f2': 'PortNet / BADR / SIMPL integrations',
  'pricing.enterprise.f3': 'SSO and advanced roles',
  'pricing.enterprise.f4': 'Dedicated hosting',
  'pricing.enterprise.f5': 'Dedicated support',

  // --- Settings ---
  'settings.title': 'Settings',
  'settings.subtitle': 'Organization, team and privacy.',
  'settings.orgSection': 'Organization',
  'settings.orgName': 'Organization name',
  'settings.city': 'City',
  'settings.iceplan': 'ICE: {ice} · Plan: {plan}',
  'settings.readonly': 'Only an administrator can change these settings.',
  'settings.saved': 'Settings saved.',
  'settings.team': 'Team ({count})',
  'settings.privacy': 'Privacy',
  'settings.demoTitle': 'Demo mode (startup)',
  'settings.demoDesc':
    'Resets the workspace with demonstration data (dossiers, alerts, audit log). Useful before a CEED / investor presentation.',
  'settings.demoReset': 'Reset demo data',
  'settings.demoConfirmTitle': 'Reset the demonstration workspace?',
  'settings.demoConfirmBody':
    'All data created during this session will be replaced with the original demonstration data.',
  'settings.demoResetDone': 'Demonstration workspace reset. Reloading…',
  'settings.reset': 'Reset',

  // --- Audit ---
  'audit.title': 'Audit log',
  'audit.subtitle':
    'Timestamped trace of all important actions: logins, dossiers, analyses, alerts, reviews and exports.',
  'audit.emptyTitle': 'Empty log',
  'audit.emptyDesc': 'Actions will appear here as they happen.',
  'audit.colDate': 'Date',
  'audit.colUser': 'User',
  'audit.colAction': 'Action',
  'audit.colDetails': 'Details',
  'audit.colRisk': 'Risk',
  'audit.tableCaption': 'Audit log of the organization',

  // --- Errors / states ---
  'error.title': 'An error occurred',
  'error.unknown': 'Unknown error.',
  'error.boundaryTitle': 'An unexpected error occurred',
  'error.boundaryBody':
    'The technical team has been notified. You can reload the page or return to the dashboard.',
  'error.boundaryCta': 'Return to dashboard',
  'error.unauthorizedTitle': 'Access denied',
  'error.unauthorizedBody':
    'This section requires the “{role}” role. Contact your organization administrator to get access.',
  'notFound.title': 'Page not found',
  'notFound.body': 'The requested address does not exist or is no longer available.',
  'notFound.cta': 'Return to dashboard',

  // --- Toast / notifications ---
  'toast.notifications': 'Notifications',
  'toast.dismiss': 'Dismiss notification',

  // --- Pagination ---
  'pagination.summary': 'Page {page} of {pages} — {total} item(s)',
  'pagination.prev': 'Previous page',
  'pagination.next': 'Next page',

  // --- Checklist statuses ---
  'check.passed': 'Compliant',
  'check.failed': 'Non-compliant',
  'check.needs_review': 'Review required',
  'check.missing': 'Missing',

  // --- Report (generated in the current UI locale) ---
  'report.section.executive_summary': 'Executive summary',
  'report.section.extracted_data': 'Extracted data',
  'report.section.fiscal_findings': 'Fiscal findings',
  'report.section.customs_findings': 'Customs findings',
  'report.section.missing_documents': 'Missing documents',
  'report.section.anomalies': 'Major anomalies',
  'report.section.recommended_actions': 'Recommended actions',
  'report.section.expert_review': 'Expert review status',
  'report.section.audit_trail': 'Audit trail summary',
  'report.section.disclaimer': 'Disclaimer',
  'report.summary':
    'Dossier “{title}” ({type}) for {client}. Overall score: {overall}/100 (level {level}). Fiscal score: {fiscal}/100 — Customs score: {customs}/100. {findings} point(s) of attention identified. {reviewSentence}',
  'report.summary.reviewRequired': 'An expert review is required before any official use.',
  'report.summary.reviewOptional':
    'No mandatory expert review, but human verification is still recommended.',
  'report.extracted.none': 'No analyzable document provided.',
  'report.extracted.line': '[{type}] confidence {confidence}% — {fields}',
  'report.fiscal.none': 'No fiscal anomaly detected.',
  'report.customs.none': 'No customs anomaly detected.',
  'report.missing.none': 'All expected documents are present.',
  'report.anomalies.none': 'No major anomaly.',
  'report.actions.ready': 'Dossier ready for transmission to the accountant / customs broker.',
  'report.expert.validated': 'Validated by an expert.',
  'report.expert.correction': 'Corrections requested by the expert.',
  'report.expert.pending': 'Awaiting expert review.',
  'report.expert.notRequired': 'Expert review not required for this risk level.',
};

