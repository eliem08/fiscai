import type { User } from '@/types/models';
import { getDb, delay, ServiceError, persist } from './db';
import { auditLogService } from './auditLogService';
import { validateLoginForm } from '@/lib/validation';
import { generateId } from '@/lib/id';

const SESSION_KEY = 'fiscai_session_v1';

export interface Session {
  user: User;
  token: string;
  createdAt: string;
}

function saveSession(session: Session | null): void {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    // localStorage unavailable: session stays in memory (store).
  }
}

export const authService = {
  restoreSession(): Session | null {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as Session) : null;
    } catch {
      return null;
    }
  },

  async login(email: string, password: string): Promise<Session> {
    const check = validateLoginForm(email, password);
    if (!check.valid) {
      throw new ServiceError('VALIDATION', check.errors[0].message);
    }
    await delay(1.5);
    const db = getDb();
    const user = db.users.find((u) => u.email.toLowerCase() === email.trim().toLowerCase());
    if (!user || user.password !== password) {
      throw new ServiceError(
        'INVALID_CREDENTIALS',
        'Identifiants invalides.',
        'Vérifiez votre e-mail et votre mot de passe. Compte démo : demo@fiscai.ma / Demo1234!',
      );
    }
    const { password: _pw, ...safeUser } = user;
    const session: Session = {
      user: safeUser,
      token: generateId('tok'),
      createdAt: new Date().toISOString(),
    };
    saveSession(session);
    auditLogService.record(
      { user: safeUser },
      'auth.login',
      'user',
      safeUser.id,
      `Connexion de ${safeUser.email}.`,
    );
    return session;
  },

  async register(name: string, email: string, password: string): Promise<Session> {
    const check = validateLoginForm(email, password);
    if (!check.valid) throw new ServiceError('VALIDATION', check.errors[0].message);
    if (!name.trim()) throw new ServiceError('VALIDATION', 'Le nom est obligatoire.');
    await delay(1.5);
    const db = getDb();
    if (db.users.some((u) => u.email.toLowerCase() === email.trim().toLowerCase())) {
      throw new ServiceError(
        'EMAIL_TAKEN',
        'Un compte existe déjà avec cet e-mail.',
        'Connectez-vous ou utilisez un autre e-mail.',
      );
    }
    const user: User & { password: string } = {
      id: generateId('usr'),
      organizationId: 'org_demo',
      name: name.trim(),
      email: email.trim().toLowerCase(),
      role: 'analyst',
      password,
    };
    db.users.push(user);
    persist();
    const { password: _pw, ...safeUser } = user;
    const session: Session = {
      user: safeUser,
      token: generateId('tok'),
      createdAt: new Date().toISOString(),
    };
    saveSession(session);
    auditLogService.record(
      { user: safeUser },
      'auth.register',
      'user',
      safeUser.id,
      `Création du compte ${safeUser.email}.`,
    );
    return session;
  },

  async logout(session: Session | null): Promise<void> {
    if (session) {
      auditLogService.record(
        { user: session.user },
        'auth.logout',
        'user',
        session.user.id,
        'Déconnexion.',
      );
    }
    saveSession(null);
  },
};
