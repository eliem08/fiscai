import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="card max-w-md p-8 text-center">
        <Compass className="mx-auto mb-3 h-8 w-8 text-brand-500" aria-hidden="true" />
        <h1 className="text-xl font-bold text-slate-900">Page introuvable</h1>
        <p className="mt-2 text-sm text-slate-600">
          L’adresse demandée n’existe pas ou n’est plus disponible.
        </p>
        <Link to="/app/dashboard" className="btn-primary mt-5 inline-flex">
          Revenir au tableau de bord
        </Link>
      </div>
    </div>
  );
}
