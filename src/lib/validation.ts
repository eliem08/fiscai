import type { DossierType } from '@/types/models';
import { sanitizeText } from './sanitize';

export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

// ---------- Dossier form ----------

export interface DossierFormValues {
  title: string;
  clientName: string;
  type: DossierType | '';
  description?: string;
  referenceBadr?: string;
}

export function validateDossierForm(values: DossierFormValues): ValidationResult {
  const errors: ValidationError[] = [];
  const title = sanitizeText(values.title ?? '');
  const clientName = sanitizeText(values.clientName ?? '');

  if (!title) errors.push({ field: 'title', message: 'Le titre du dossier est obligatoire.' });
  else if (title.length < 3)
    errors.push({ field: 'title', message: 'Le titre doit contenir au moins 3 caractères.' });

  if (!clientName)
    errors.push({ field: 'clientName', message: 'Le nom du client est obligatoire.' });

  if (!values.type)
    errors.push({ field: 'type', message: 'Veuillez sélectionner un type de dossier.' });

  if (values.referenceBadr && !/^[A-Za-z0-9\-/]{4,30}$/.test(values.referenceBadr))
    errors.push({
      field: 'referenceBadr',
      message: 'Référence BADR invalide (4 à 30 caractères alphanumériques).',
    });

  return { valid: errors.length === 0, errors };
}

// ---------- Login form ----------

export function validateLoginForm(email: string, password: string): ValidationResult {
  const errors: ValidationError[] = [];
  if (!email) errors.push({ field: 'email', message: "L'adresse e-mail est obligatoire." });
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    errors.push({ field: 'email', message: 'Adresse e-mail invalide.' });
  if (!password) errors.push({ field: 'password', message: 'Le mot de passe est obligatoire.' });
  else if (password.length < 8)
    errors.push({
      field: 'password',
      message: 'Le mot de passe doit contenir au moins 8 caractères.',
    });
  return { valid: errors.length === 0, errors };
}

// ---------- File upload ----------

export const ALLOWED_FILE_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xml', 'docx'];
export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/xml',
  'application/xml',
];
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

export interface FileCheck {
  valid: boolean;
  reason?: string;
}

export function validateUploadFile(file: { name: string; size: number; type: string }): FileCheck {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!ALLOWED_FILE_EXTENSIONS.includes(ext)) {
    return {
      valid: false,
      reason: `Type de fichier non supporté (.${ext}). Formats acceptés : ${ALLOWED_FILE_EXTENSIONS.map((e) => '.' + e).join(', ')}.`,
    };
  }
  if (file.type && !ALLOWED_MIME_TYPES.includes(file.type)) {
    return { valid: false, reason: `Type MIME non autorisé (${file.type}).` };
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      reason: `Fichier trop volumineux (${(file.size / 1024 / 1024).toFixed(1)} Mo). Limite : 10 Mo.`,
    };
  }
  if (file.size === 0) {
    return { valid: false, reason: 'Le fichier est vide.' };
  }
  return { valid: true };
}
