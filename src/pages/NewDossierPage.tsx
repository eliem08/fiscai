import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type { DossierType } from '@/types/models';
import { DOSSIER_TYPE_LABELS } from '@/lib/constants';
import { validateDossierForm } from '@/lib/validation';
import { dossierService } from '@/services/dossierService';
import { useCurrentUser } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { Disclaimer } from '@/components/domain/Disclaimer';

export function NewDossierPage() {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [clientName, setClientName] = useState('');
  const [type, setType] = useState<DossierType | ''>('');
  const [description, setDescription] = useState('');
  const [referenceBadr, setReferenceBadr] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    setSubmitError(null);
    const values = { title, clientName, type, description, referenceBadr };
    const check = validateDossierForm(values);
    if (!check.valid) {
      setErrors(Object.fromEntries(check.errors.map((er) => [er.field, er.message])));
      return;
    }
    setErrors({});
    setSaving(true);
    try {
      const dossier = await dossierService.create({ user }, values);
      toast('success', `Dossier « ${dossier.title} » créé.`);
      navigate(`/app/dossiers/${dossier.id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur lors de la création du dossier.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Nouveau dossier</h1>
        <p className="text-sm text-slate-500">
          Créez un dossier, ajoutez les documents, puis lancez l’analyse IA de pré-contrôle.
        </p>
      </div>

      <form className="card space-y-5 p-6" onSubmit={(e) => void handleSubmit(e)} noValidate>
        <fieldset>
          <legend className="label">Type de dossier *</legend>
          <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Type de dossier">
            {(Object.entries(DOSSIER_TYPE_LABELS) as [DossierType, string][]).map(
              ([value, label]) => (
                <label
                  key={value}
                  className={`cursor-pointer rounded-xl border p-4 text-center text-sm font-medium transition ${
                    type === value
                      ? 'border-brand-500 bg-brand-50 text-brand-800'
                      : 'border-slate-200 hover:border-brand-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="dossier-type"
                    value={value}
                    checked={type === value}
                    onChange={() => setType(value)}
                    className="sr-only"
                  />
                  {label}
                </label>
              ),
            )}
          </div>
          {errors.type && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {errors.type}
            </p>
          )}
        </fieldset>

        <div>
          <label className="label" htmlFor="dossier-title">
            Titre du dossier *
          </label>
          <input
            id="dossier-title"
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex. Import composants électroniques — Shenzhen"
            aria-invalid={!!errors.title}
          />
          {errors.title && (
            <p role="alert" className="mt-1 text-sm text-red-700" data-testid="title-error">
              {errors.title}
            </p>
          )}
        </div>

        <div>
          <label className="label" htmlFor="dossier-client">
            Client / entité concernée *
          </label>
          <input
            id="dossier-client"
            className="input"
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
            placeholder="Ex. ElectroMaroc SARL"
            aria-invalid={!!errors.clientName}
          />
          {errors.clientName && (
            <p role="alert" className="mt-1 text-sm text-red-700">
              {errors.clientName}
            </p>
          )}
        </div>

        <div>
          <label className="label" htmlFor="dossier-ref">
            Référence BADR / PortNet (optionnel)
          </label>
          <input
            id="dossier-ref"
            className="input"
            value={referenceBadr}
            onChange={(e) => setReferenceBadr(e.target.value)}
            placeholder="Ex. BADR-2026-11842"
            aria-invalid={!!errors.referenceBadr}
          />
          {errors.referenceBadr && (
            <p role="alert" className="mt-1 text-sm text-red-700">
              {errors.referenceBadr}
            </p>
          )}
        </div>

        <div>
          <label className="label" htmlFor="dossier-desc">
            Description (optionnel)
          </label>
          <textarea
            id="dossier-desc"
            className="input"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Contexte, marchandises, échéances…"
          />
        </div>

        {submitError && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {submitError}
          </p>
        )}

        <div className="flex justify-end gap-3">
          <button type="button" className="btn-secondary" onClick={() => navigate('/app/dossiers')}>
            Annuler
          </button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Création…' : 'Créer le dossier'}
          </button>
        </div>
      </form>
      <Disclaimer />
    </div>
  );
}
