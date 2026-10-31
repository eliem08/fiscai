import { useEffect, useState, type FormEvent } from 'react';
import type { Organization, User } from '@/types/models';
import { organizationService } from '@/services/organizationService';
import { resetDb } from '@/services/db';
import { useCurrentUser, hasRole } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { PRIVACY_NOTICE } from '@/lib/constants';
import { Disclaimer } from '@/components/domain/Disclaimer';
import { Modal } from '@/components/ui/Modal';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';

export function SettingsPage() {
  const user = useCurrentUser();
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [city, setCity] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const isAdmin = hasRole(user, 'admin');

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    Promise.all([
      organizationService.get(user.organizationId),
      organizationService.members(user.organizationId),
    ])
      .then(([o, m]) => {
        if (!cancelled) {
          setOrg(o);
          setMembers(m);
          setName(o.name);
          setCity(o.city);
        }
      })
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    if (!name.trim()) {
      toast('error', 'Le nom de l’organisation est obligatoire.');
      return;
    }
    setSaving(true);
    try {
      const updated = await organizationService.update({ user }, { name, city });
      setOrg(updated);
      toast('success', 'Paramètres enregistrés.');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Enregistrement impossible.');
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    resetDb();
    setConfirmReset(false);
    toast('info', 'Espace de démonstration réinitialisé. Rechargement…');
    setTimeout(() => window.location.reload(), 800);
  }

  if (error) return <ErrorState error={error} onRetry={() => setReloadKey((k) => k + 1)} />;
  if (!org)
    return (
      <div className="space-y-3" aria-busy="true">
        <SkeletonCard />
      </div>
    );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Paramètres</h1>
        <p className="text-sm text-slate-500">Organisation, équipe et confidentialité.</p>
      </div>

      <form
        className="card space-y-4 p-6"
        onSubmit={(e) => void handleSave(e)}
        aria-label="Paramètres de l’organisation"
      >
        <h2 className="text-lg font-semibold text-slate-900">Organisation</h2>
        <div>
          <label className="label" htmlFor="org-name">
            Nom de l’organisation
          </label>
          <input
            id="org-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!isAdmin}
          />
        </div>
        <div>
          <label className="label" htmlFor="org-city">
            Ville
          </label>
          <input
            id="org-city"
            className="input"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            disabled={!isAdmin}
          />
        </div>
        <p className="text-xs text-slate-500">
          ICE : {org.ice} · Plan : <span className="font-semibold uppercase">{org.plan}</span>
        </p>
        {isAdmin ? (
          <div className="flex justify-end">
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </div>
        ) : (
          <p className="text-sm text-slate-500" data-testid="settings-readonly">
            Seul un administrateur peut modifier ces paramètres.
          </p>
        )}
      </form>

      <section className="card p-6" aria-label="Membres de l’équipe">
        <h2 className="text-lg font-semibold text-slate-900">Équipe ({members.length})</h2>
        <ul className="mt-3 divide-y divide-slate-100">
          {members.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-700">
                {m.name} <span className="text-slate-400">· {m.email}</span>
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold capitalize text-slate-600">
                {m.role}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card p-6" aria-label="Confidentialité des données">
        <h2 className="text-lg font-semibold text-slate-900">Confidentialité</h2>
        <p className="mt-2 text-sm text-slate-600" data-testid="privacy-notice">
          {PRIVACY_NOTICE}
        </p>
      </section>

      {isAdmin && (
        <section className="card border-amber-300 p-6" aria-label="Mode démonstration">
          <h2 className="text-lg font-semibold text-slate-900">Mode démonstration (startup)</h2>
          <p className="mt-2 text-sm text-slate-600">
            Réinitialise l’espace de travail avec les données de démonstration (dossiers, alertes,
            journal d’audit). Utile avant une présentation CEED / investisseurs.
          </p>
          <button
            type="button"
            className="btn-secondary mt-4"
            onClick={() => setConfirmReset(true)}
            data-testid="reset-demo"
          >
            Réinitialiser les données de démo
          </button>
        </section>
      )}

      <Disclaimer />

      <Modal
        open={confirmReset}
        title="Réinitialiser l’espace de démonstration ?"
        onClose={() => setConfirmReset(false)}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setConfirmReset(false)}>
              Annuler
            </button>
            <button type="button" className="btn-danger" onClick={handleReset}>
              Réinitialiser
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          Toutes les données créées pendant cette session seront remplacées par les données de
          démonstration d’origine.
        </p>
      </Modal>
    </div>
  );
}
