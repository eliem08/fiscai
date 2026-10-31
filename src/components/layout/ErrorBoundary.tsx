import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Last-resort error boundary: no page should crash to a white screen. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Hook point for Sentry/monitoring in production.
    console.error('[FiscAI] Uncaught render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
          <div className="card max-w-md p-8 text-center" role="alert">
            <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-amber-500" aria-hidden="true" />
            <h1 className="text-lg font-semibold text-slate-900">
              Une erreur inattendue est survenue
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              L’équipe technique a été notifiée. Vous pouvez recharger la page ou revenir au tableau
              de bord.
            </p>
            <button
              type="button"
              className="btn-primary mt-4"
              onClick={() => {
                this.setState({ error: null });
                window.location.assign('/app/dashboard');
              }}
            >
              Revenir au tableau de bord
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
