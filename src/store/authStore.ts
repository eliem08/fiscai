import { create } from 'zustand';
import type { Role, User } from '@/types/models';
import { authService, type Session } from '@/services/authService';

interface AuthState {
  session: Session | null;
  status: 'idle' | 'loading' | 'authenticated' | 'error';
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  session: authService.restoreSession(),
  status: authService.restoreSession() ? 'authenticated' : 'idle',
  error: null,

  async login(email, password) {
    set({ status: 'loading', error: null });
    try {
      const session = await authService.login(email, password);
      set({ session, status: 'authenticated' });
    } catch (e) {
      set({ status: 'error', error: e instanceof Error ? e.message : 'Erreur de connexion.' });
      throw e;
    }
  },

  async register(name, email, password) {
    set({ status: 'loading', error: null });
    try {
      const session = await authService.register(name, email, password);
      set({ session, status: 'authenticated' });
    } catch (e) {
      set({ status: 'error', error: e instanceof Error ? e.message : 'Erreur d’inscription.' });
      throw e;
    }
  },

  async logout() {
    await authService.logout(get().session);
    set({ session: null, status: 'idle', error: null });
  },

  clearError: () => set({ error: null }),
}));

export function useCurrentUser(): User | null {
  return useAuthStore((s) => s.session?.user ?? null);
}

const ROLE_RANK: Record<Role, number> = { viewer: 0, analyst: 1, expert: 2, admin: 3 };

export function hasRole(user: User | null, minimum: Role): boolean {
  if (!user) return false;
  return ROLE_RANK[user.role] >= ROLE_RANK[minimum];
}
