import { Link } from 'react-router-dom';
import { Check, ShieldCheck } from 'lucide-react';
import { APP_NAME, LEGAL_DISCLAIMER } from '@/lib/constants';

export interface Plan {
  id: string;
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  highlighted?: boolean;
}

export const PLANS: Plan[] = [
  {
    id: 'starter',
    name: 'Starter',
    price: '490 MAD',
    period: '/mois',
    description: 'Pour les PME qui débutent avec l’import/export.',
    features: [
      '10 dossiers / mois',
      'Analyse IA fiscale et douanière',
      'Alertes et checklist',
      'Rapports de pré-contrôle',
      'Support e-mail',
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '1 490 MAD',
    period: '/mois',
    description: 'Pour cabinets comptables et transitaires.',
    features: [
      '60 dossiers / mois',
      'Multi-clients et multi-utilisateurs',
      'Revue experte intégrée',
      'Journal d’audit complet',
      'Support prioritaire',
    ],
    highlighted: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Sur devis',
    period: '',
    description: 'Pour groupes, institutions et gros volumes.',
    features: [
      'Dossiers illimités',
      'Intégrations PortNet / BADR / SIMPL',
      'SSO et rôles avancés',
      'Hébergement dédié',
      'Accompagnement dédié',
    ],
  },
];

export function PricingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Link to="/" className="flex items-center gap-2">
          <span className="rounded-lg bg-brand-600 p-1.5 text-white" aria-hidden="true">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="text-lg font-bold text-slate-900">{APP_NAME}</span>
        </Link>
        <Link to="/login" className="btn-primary">
          Se connecter
        </Link>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-12">
        <h1 className="text-center text-3xl font-extrabold text-slate-900">
          Tarifs simples et transparents
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-center text-slate-600">
          Choisissez le plan adapté à votre volume de dossiers. Sans engagement, annulable à tout
          moment.
        </p>
        <div className="mt-10 grid gap-6 lg:grid-cols-3" data-testid="pricing-grid">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              data-testid="pricing-card"
              data-plan={plan.id}
              className={`card flex flex-col p-6 ${plan.highlighted ? 'border-brand-500 ring-2 ring-brand-500' : ''}`}
            >
              {plan.highlighted && (
                <span className="mb-2 self-start rounded-full bg-brand-600 px-3 py-0.5 text-xs font-semibold text-white">
                  Recommandé
                </span>
              )}
              <h2 className="text-lg font-bold text-slate-900">{plan.name}</h2>
              <p className="mt-1 text-sm text-slate-500">{plan.description}</p>
              <p className="mt-4">
                <span className="text-3xl font-extrabold text-slate-900">{plan.price}</span>
                <span className="text-sm text-slate-500">{plan.period}</span>
              </p>
              <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-600">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`mt-6 ${plan.highlighted ? 'btn-primary' : 'btn-secondary'} w-full`}
              >
                {plan.id === 'enterprise' ? 'Nous contacter' : 'Commencer'}
              </Link>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-10 max-w-2xl text-center text-xs text-slate-400">
          {LEGAL_DISCLAIMER}
        </p>
      </main>
    </div>
  );
}
