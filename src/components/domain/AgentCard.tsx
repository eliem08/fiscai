import { Bot, CheckCircle2, CircleDashed, Loader2, ShieldAlert, XCircle } from 'lucide-react';
import type { AgentRun, AgentStatus } from '@/types/models';
import { useTranslation } from '@/i18n';

const STATUS_META: Record<AgentStatus, { className: string; icon: JSX.Element }> = {
  idle: { className: 'text-slate-500 bg-slate-100 border-slate-300', icon: <CircleDashed className="h-4 w-4" aria-hidden="true" /> },
  running: { className: 'text-sky-700 bg-sky-50 border-sky-300', icon: <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> },
  completed: { className: 'text-emerald-700 bg-emerald-50 border-emerald-300', icon: <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> },
  failed: { className: 'text-red-700 bg-red-50 border-red-300', icon: <XCircle className="h-4 w-4" aria-hidden="true" /> },
  needs_review: { className: 'text-amber-700 bg-amber-50 border-amber-300', icon: <ShieldAlert className="h-4 w-4" aria-hidden="true" /> },
};

export function AgentCard({ run }: { run: AgentRun }) {
  const { t } = useTranslation();
  const meta = STATUS_META[run.status];
  return (
    <div className="card p-5" data-testid="agent-card" data-agent={run.agentId} data-status={run.status}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-brand-50 p-2 text-brand-600" aria-hidden="true">
            <Bot className="h-5 w-5" />
          </span>
          <div>
            <h3 className="font-semibold text-slate-900">{run.agentName}</h3>
            <p className="text-xs text-slate-500">{run.description}</p>
          </div>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${meta.className}`}
        >
          {meta.icon} {t(`agent.status.${run.status}`)}
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {t('agent.confidence', { value: Math.round(run.confidence * 100) })}
      </p>
      {run.findings.length > 0 && (
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-700">
          {run.findings.slice(0, 4).map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
      {run.evidence.length > 0 && (
        <details className="mt-2 text-xs text-slate-500">
          <summary className="cursor-pointer font-medium">{t('agent.evidence')}</summary>
          <ul className="mt-1 list-inside list-disc space-y-1">
            {run.evidence.slice(0, 4).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="mt-2 text-xs text-slate-600">
        <span className="font-medium">{t('common.recommendedAction')} :</span> {run.recommendedAction}
      </p>
    </div>
  );
}
