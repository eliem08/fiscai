import { Link } from 'react-router-dom';
import { Bell, Bot, FileSearch, FileText, ShieldCheck, Workflow } from 'lucide-react';
import { APP_NAME, LEGAL_DISCLAIMER } from '@/lib/constants';
import { LanguageSelector } from '@/components/layout/LanguageSelector';

const FEATURES = [
  {
    icon: FileSearch,
    title: 'Pré-contrôle des dossiers',
    text: 'Analyse des factures, documents fiscaux et dossiers import/export avant transmission à vos comptables, transitaires et aux flux PortNet/BADR.',
  },
  {
    icon: Bot,
    title: 'Agents IA spécialisés',
    text: 'Agents fiscal, douane, réglementation, conformité et anomalies travaillent en pipeline, avec preuves et niveau de confiance.',
  },
  {
    icon: ShieldCheck,
    title: 'Score de risque',
    text: 'Scores fiscal et douanier 0-100, détection des documents manquants et incohérences TVA / code SH.',
  },
  {
    icon: Bell,
    title: 'Alertes et vigilance',
    text: 'Alertes hiérarchisées (critique → faible) avec suivi de statut jusqu’à résolution.',
  },
  {
    icon: Workflow,
    title: 'Revue experte',
    text: 'Aucune conclusion officielle sans validation humaine : workflow de revue intégré et journalisé.',
  },
  {
    icon: FileText,
    title: 'Rapports prêts à transmettre',
    text: 'Rapports structurés (synthèse, constats, actions, piste d’audit) pour vos experts et partenaires.',
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-brand-600 p-1.5 text-white" aria-hidden="true">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="text-lg font-bold text-slate-900">{APP_NAME}</span>
        </div>
        <nav aria-label="Navigation publique" className="flex items-center gap-4">
          <Link to="/pricing" className="text-sm font-medium text-slate-600 hover:text-brand-700">
            Tarifs
          </Link>
          <LanguageSelector />
          <Link to="/login" className="btn-primary">
            Se connecter
          </Link>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-6 py-16 text-center lg:py-24">
          <p className="mx-auto inline-block rounded-full border border-brand-200 bg-brand-50 px-4 py-1 text-xs font-semibold text-brand-700">
            Fiscalité · TVA · Douane — Maroc
          </p>
          <h1 className="mx-auto mt-5 max-w-3xl text-4xl font-extrabold tracking-tight text-slate-900 lg:text-5xl">
            Pré-contrôlez vos dossiers fiscaux et douaniers avant qu’ils ne partent
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
            {APP_NAME} analyse vos factures et dossiers import/export avec des agents IA, détecte
            les documents manquants et les incohérences TVA/douane, et prépare un rapport de risque
            — avant vos échanges avec comptables, transitaires, DGI, PortNet ou BADR.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <Link to="/register" className="btn-primary px-6 py-3 text-base">
              Essayer la démo
            </Link>
            <Link to="/pricing" className="btn-secondary px-6 py-3 text-base">
              Voir les tarifs
            </Link>
          </div>
        </section>

        <section aria-label="Fonctionnalités" className="bg-slate-50 py-16">
          <div className="mx-auto grid max-w-6xl gap-6 px-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="card p-6">
                <f.icon className="h-6 w-6 text-brand-600" aria-hidden="true" />
                <h2 className="mt-3 font-semibold text-slate-900">{f.title}</h2>
                <p className="mt-2 text-sm text-slate-600">{f.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-4xl px-6 py-12">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
            <strong className="text-slate-800">Avertissement : </strong>
            {LEGAL_DISCLAIMER}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-400">
        © 2026 {APP_NAME} — Outil d’aide à la décision. Ne remplace ni comptable, ni transitaire, ni
        administration fiscale ou douanière.
      </footer>
    </div>
  );
}
