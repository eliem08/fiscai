import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { APP_NAME, PRIVACY_NOTICE } from '@/lib/constants';
import { validateLoginForm } from '@/lib/validation';
import { useAuthStore } from '@/store/authStore';

export function RegisterPage() {
  const navigate = useNavigate();
  const { register, status } = useAuthStore();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const loading = status === 'loading';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = 'Le nom est obligatoire.';
    const check = validateLoginForm(email, password);
    for (const er of check.errors) next[er.field] = er.message;
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    try {
      await register(name, email, password);
      navigate('/app/dashboard');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur d’inscription.');
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2">
          <span className="rounded-lg bg-brand-600 p-1.5 text-white" aria-hidden="true">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="text-xl font-bold text-slate-900">{APP_NAME}</span>
        </div>
        <form className="card p-8" onSubmit={(e) => void handleSubmit(e)} noValidate>
          <h1 className="text-lg font-semibold text-slate-900">Créer un compte</h1>
          <div className="mt-5">
            <label className="label" htmlFor="reg-name">
              Nom complet
            </label>
            <input
              id="reg-name"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <p role="alert" className="mt-1 text-sm text-red-700">
                {errors.name}
              </p>
            )}
          </div>
          <div className="mt-4">
            <label className="label" htmlFor="reg-email">
              Adresse e-mail professionnelle
            </label>
            <input
              id="reg-email"
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={!!errors.email}
            />
            {errors.email && (
              <p role="alert" className="mt-1 text-sm text-red-700">
                {errors.email}
              </p>
            )}
          </div>
          <div className="mt-4">
            <label className="label" htmlFor="reg-password">
              Mot de passe (8 caractères min.)
            </label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!errors.password}
            />
            {errors.password && (
              <p role="alert" className="mt-1 text-sm text-red-700">
                {errors.password}
              </p>
            )}
          </div>
          {submitError && (
            <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {submitError}
            </p>
          )}
          <button type="submit" className="btn-primary mt-6 w-full" disabled={loading}>
            {loading ? 'Création du compte…' : 'Créer mon compte'}
          </button>
          <p className="mt-4 text-xs text-slate-400">{PRIVACY_NOTICE}</p>
          <p className="mt-4 text-center text-sm text-slate-500">
            Déjà inscrit ?{' '}
            <Link to="/login" className="font-medium text-brand-700 underline">
              Se connecter
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
