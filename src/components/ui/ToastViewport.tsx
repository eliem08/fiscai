import { CheckCircle2, Info, TriangleAlert, XCircle, X } from 'lucide-react';
import { useToastStore } from '@/store/toastStore';

const ICONS = {
  success: <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden="true" />,
  error: <XCircle className="h-5 w-5 text-red-600" aria-hidden="true" />,
  warning: <TriangleAlert className="h-5 w-5 text-amber-600" aria-hidden="true" />,
  info: <Info className="h-5 w-5 text-sky-600" aria-hidden="true" />,
};

export function ToastViewport() {
  const { toasts, dismiss } = useToastStore();
  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className="pointer-events-auto flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-lg"
        >
          {ICONS[t.kind]}
          <p className="flex-1 text-sm text-slate-700">{t.message}</p>
          <button
            type="button"
            aria-label="Fermer la notification"
            onClick={() => dismiss(t.id)}
            className="text-slate-400 hover:text-slate-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
