import type { ReactNode } from 'react';

interface KpiCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: ReactNode;
  tone?: 'default' | 'warning' | 'danger' | 'success';
}

const TONES = {
  default: 'text-slate-900',
  warning: 'text-amber-700',
  danger: 'text-red-700',
  success: 'text-emerald-700',
};

export function KpiCard({ label, value, hint, icon, tone = 'default' }: KpiCardProps) {
  return (
    <div className="card p-5" data-testid="kpi-card">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        {icon && (
          <span className="text-brand-600" aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      <p className={`mt-2 text-3xl font-bold ${TONES[tone]}`} data-testid="kpi-value">
        {value}
      </p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
