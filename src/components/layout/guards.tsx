import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { Role } from '@/types/models';
import { hasRole, useAuthStore, useCurrentUser } from '@/store/authStore';
import { ShieldX } from 'lucide-react';

/** Authentication guard: redirects unauthenticated visitors to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const session = useAuthStore((s) => s.session);
  const location = useLocation();
  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

/** Role-based access guard: shows a clear unauthorized state instead of crashing. */
export function RequireRole({ minimum, children }: { minimum: Role; children: ReactNode }) {
  const user = useCurrentUser();
  if (!hasRole(user, minimum)) {
    return (
      <div
        className="card mx-auto max-w-lg p-8 text-center"
        role="alert"
        data-testid="unauthorized"
      >
        <ShieldX className="mx-auto mb-3 h-8 w-8 text-red-500" aria-hidden="true" />
        <h2 className="text-lg font-semibold text-slate-900">Accès non autorisé</h2>
        <p className="mt-2 text-sm text-slate-600">
          Cette section requiert le rôle « {minimum} ». Contactez l’administrateur de votre
          organisation pour obtenir l’accès.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
