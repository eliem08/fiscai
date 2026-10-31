import type { Report } from '@/types/models';
import { useTranslation } from '@/i18n';
import { formatDateTime } from '@/lib/format';
import { RiskBadge } from './RiskBadge';

export function ReportPreview({ report }: { report: Report }) {
  const { t } = useTranslation();
  return (
    <article className="card p-6" data-testid="report-preview" aria-label={report.dossierTitle}>
      <header className="border-b border-slate-200 pb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
          {t('report.heading')}
        </p>
        <h2 className="mt-1 text-xl font-bold text-slate-900">{report.dossierTitle}</h2>
        <p className="mt-1 text-sm text-slate-500">
          {report.organizationName} · {t('report.client')} : {report.clientName} ·{' '}
          {formatDateTime(report.date)}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <RiskBadge level={report.scores.level} score={report.scores.overall} />
          <span className="text-slate-600">
            {t('dossier.fiscalScore')} : {report.scores.fiscal}/100
          </span>
          <span className="text-slate-600">
            {t('dossier.customsScore')} : {report.scores.customs}/100
          </span>
        </div>
      </header>
      {report.sections.map((section) => (
        <section key={section.key} className="border-b border-slate-100 py-4 last:border-0" data-section={section.key}>
          <h3 className="text-sm font-bold uppercase tracking-wide text-slate-700">{section.title}</h3>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-600">{section.content}</p>
        </section>
      ))}
    </article>
  );
}
