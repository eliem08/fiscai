import { NavLink } from 'react-router-dom';
import {
  Bell,
  Bot,
  FileText,
  Files,
  FolderKanban,
  LayoutDashboard,
  ScrollText,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import { APP_NAME } from '@/lib/constants';
import { useCurrentUser, hasRole } from '@/store/authStore';

const NAV_ITEMS = [
  { to: '/app/dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/app/dossiers', label: 'Dossiers', icon: FolderKanban },
  { to: '/app/documents', label: 'Documents', icon: Files },
  { to: '/app/agents', label: 'Agents IA', icon: Bot },
  { to: '/app/alerts', label: 'Alertes', icon: Bell },
  {
    to: '/app/expert-review',
    label: 'Revue experte',
    icon: ShieldCheck,
    minRole: 'expert' as const,
  },
  { to: '/app/reports', label: 'Rapports', icon: FileText },
  { to: '/app/audit', label: 'Journal d’audit', icon: ScrollText, minRole: 'admin' as const },
  { to: '/app/settings', label: 'Paramètres', icon: Settings },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const user = useCurrentUser();
  return (
    <nav aria-label="Navigation principale" className="flex h-full flex-col" data-testid="sidebar">
      <div className="flex items-center gap-2 px-5 py-5">
        <span className="rounded-lg bg-brand-600 p-1.5 text-white" aria-hidden="true">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="text-lg font-bold text-white">{APP_NAME}</span>
      </div>
      <ul className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.filter((item) => !item.minRole || hasRole(user, item.minRole)).map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-600 text-white'
                    : 'text-brand-100 hover:bg-brand-800 hover:text-white'
                }`
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <p className="px-5 py-4 text-xs text-brand-300">
        Pré-contrôle IA — les résultats exigent une validation experte.
      </p>
    </nav>
  );
}
