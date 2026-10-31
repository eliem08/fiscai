import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { LogOut, Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { LanguageSelector } from './LanguageSelector';
import { ToastViewport } from '@/components/ui/ToastViewport';
import { useAuthStore, useCurrentUser } from '@/store/authStore';

export function AppLayout() {
  const user = useCurrentUser();
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 bg-brand-950 lg:block">
        <Sidebar />
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-brand-950">
            <button
              type="button"
              className="absolute right-3 top-4 text-brand-200"
              aria-label="Fermer le menu"
              onClick={() => setMobileOpen(false)}
            >
              <X className="h-5 w-5" />
            </button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:px-8">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            aria-label="Ouvrir le menu de navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-sm text-slate-500 lg:block">
            Espace de travail : <strong className="text-slate-700">Atlas Import Export SARL</strong>
          </div>
          <div className="flex items-center gap-4">
            <LanguageSelector />
            {user && (
              <span className="text-sm text-slate-600" data-testid="current-user">
                {user.name} · <span className="capitalize text-slate-400">{user.role}</span>
              </span>
            )}
            <button
              type="button"
              className="btn-secondary px-3 py-1.5"
              onClick={() => void handleLogout()}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" /> Déconnexion
            </button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 lg:px-8" id="main-content">
          <Outlet />
        </main>
      </div>
      <ToastViewport />
    </div>
  );
}
