import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { APP_NAME } from '@/lib/constants';
import { validateLoginForm } from '@/lib/validation';
import { useAuthStore } from '@/store/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const { login, status } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const loading = status === 'loading';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    const check = validateLoginForm(email, password);
    if (!check.valid) {
      setFieldErrors(Object.fromEntries(check.errors.map((er) => [er.field, er.message])));
      return;
    }
    setFieldErrors({});
    try {
      await login(email, password);
      navigate(location.state?.from ?? '/app/dashboard');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur de connexion.');
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
          <h1 className="text-lg font-semibold text-slate-900">Connexion</h1>
          <p className="mt-1 text-sm text-slate-500">
            Compte démo : <code>demo@fiscai.ma</code> / <code>Demo1234!</code>
          </p>

          <div className="mt-5">
            <label className="label" htmlFor="login-email">
              Adresse e-mail
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={!!fieldErrors.email}
              aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
            />
            {fieldErrors.email && (
              <p id="login-email-error" role="alert" className="mt-1 text-sm text-red-700">
                {fieldErrors.email}
              </p>
            )}
          </div>
          <div className="mt-4">
            <label className="label" htmlFor="login-password">
              Mot de passe
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!fieldErrors.password}
              aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
            />
            {fieldErrors.password && (
              <p id="login-password-error" role="alert" className="mt-1 text-sm text-red-700">
                {fieldErrors.password}
              </p>
            )}
          </div>

          {submitError && (
            <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {submitError}
            </p>
          )}

          <button type="submit" className="btn-primary mt-6 w-full" disabled={loading}>
            {loading ? 'Connexion en cours…' : 'Se connecter'}
          </button>
          <p className="mt-4 text-center text-sm text-slate-500">
            Pas de compte ?{' '}
            <Link to="/register" className="font-medium text-brand-700 underline">
              Créer un compte
            </Link>
          </p>
        </form>
        <p className="mt-4 text-center text-xs text-slate-400">
          <Link to="/" className="underline">
            ← Retour à l’accueil
          </Link>
        </p>
      </div>
    </div>
  );
}
