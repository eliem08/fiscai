import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LandingPage } from './LandingPage';
import { LoginPage } from './LoginPage';
import { DashboardPage } from './DashboardPage';
import { PricingPage, PLANS } from './PricingPage';
import { AlertsPage } from './AlertsPage';
import { ExpertReviewPage } from './ExpertReviewPage';
import { NewDossierPage } from './NewDossierPage';
import { AgentsPage } from './AgentsPage';
import { Sidebar } from '@/components/layout/Sidebar';
import { RequireRole } from '@/components/layout/guards';
import { useAuthStore } from '@/store/authStore';
import { getDb, persist } from '@/services/db';
import type { User } from '@/types/models';

const analyst: User = {
  id: 'usr_analyst',
  organizationId: 'org_demo',
  name: 'Karim Bennis',
  email: 'demo@fiscai.ma',
  role: 'analyst',
};
const expert: User = { ...analyst, id: 'usr_expert', name: 'Salma Idrissi', role: 'expert' };

function signIn(user: User) {
  useAuthStore.setState({
    session: { user, token: 'tok_test', createdAt: new Date().toISOString() },
    status: 'authenticated',
    error: null,
  });
}

function renderPage(ui: React.ReactElement, path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useAuthStore.setState({ session: null, status: 'idle', error: null });
});

describe('LandingPage', () => {
  it('presents the value proposition, navigation and the legal disclaimer', () => {
    renderPage(<LandingPage />);
    expect(screen.getAllByText(/FiscAI PreClear/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /se connecter/i })).toHaveAttribute('href', '/login');
    expect(screen.getByText(/assistance au pré-contrôle fiscal et douanier/)).toBeInTheDocument();
    expect(screen.getByTestId('language-selector')).toBeInTheDocument();
  });
});

describe('Login flow', () => {
  it('shows validation errors for empty fields without calling the backend', async () => {
    renderPage(<LoginPage />);
    await userEvent.click(screen.getByRole('button', { name: /se connecter/i }));
    expect(await screen.findAllByRole('alert')).not.toHaveLength(0);
    expect(useAuthStore.getState().session).toBeNull();
  });

  it('signs in with demo credentials', async () => {
    renderPage(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse e-mail/i), 'demo@fiscai.ma');
    await userEvent.type(screen.getByLabelText(/mot de passe/i), 'Demo1234!');
    await userEvent.click(screen.getByRole('button', { name: /se connecter/i }));
    await waitFor(() => expect(useAuthStore.getState().session?.user.email).toBe('demo@fiscai.ma'));
  });

  it('surfaces an invalid-credentials error', async () => {
    renderPage(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse e-mail/i), 'demo@fiscai.ma');
    await userEvent.type(screen.getByLabelText(/mot de passe/i), 'WrongPass99!');
    await userEvent.click(screen.getByRole('button', { name: /se connecter/i }));
    expect(await screen.findByText(/identifiants invalides/i)).toBeInTheDocument();
  });
});

describe('DashboardPage', () => {
  it('shows KPI cards with values from the workspace', async () => {
    signIn(analyst);
    renderPage(<DashboardPage />);
    const grid = await screen.findByTestId('kpi-grid');
    const cards = within(grid).getAllByTestId('kpi-card');
    expect(cards).toHaveLength(4);
    expect(grid).toHaveTextContent('Dossiers actifs');
    expect(grid).toHaveTextContent('Alertes ouvertes');
    expect(screen.getAllByTestId('dossier-card').length).toBeGreaterThan(0);
  });

  it('shows an empty state when the workspace has no dossiers', async () => {
    signIn(analyst);
    const db = getDb();
    db.dossiers = [];
    db.alerts = [];
    persist();
    renderPage(<DashboardPage />);
    expect(await screen.findByTestId('empty-state')).toHaveTextContent(/aucun dossier/i);
  });
});

describe('PricingPage', () => {
  it('renders the three plans with correct details', () => {
    renderPage(<PricingPage />);
    const cards = screen.getAllByTestId('pricing-card');
    expect(cards).toHaveLength(PLANS.length);
    expect(cards[0]).toHaveTextContent('Starter');
    expect(cards[0]).toHaveTextContent('490 MAD');
    expect(cards[1]).toHaveTextContent('Pro');
    expect(cards[1]).toHaveTextContent('Recommandé');
    expect(cards[2]).toHaveTextContent('Sur devis');
  });
});

describe('AlertsPage', () => {
  it('lists alerts with severity badges and supports filtering', async () => {
    signIn(analyst);
    renderPage(<AlertsPage />);
    const list = await screen.findByTestId('alert-list');
    expect(within(list).getAllByTestId('alert-card').length).toBeGreaterThan(0);
    await userEvent.selectOptions(screen.getByLabelText(/sévérité/i), 'critical');
    await waitFor(() => {
      const cards = screen.getAllByTestId('alert-card');
      expect(cards.every((c) => c.getAttribute('data-severity') === 'critical')).toBe(true);
    });
  });
});

describe('ExpertReviewPage', () => {
  it('validates the review form before saving', async () => {
    signIn(expert);
    renderPage(<ExpertReviewPage />);
    const awaiting = await screen.findByTestId('awaiting-list');
    await userEvent.click(within(awaiting).getAllByRole('button')[0]);
    await screen.findByTestId('review-form');
    await userEvent.click(screen.getByTestId('submit-review'));
    expect(await screen.findByTestId('review-error')).toHaveTextContent(/décision/i);
    await userEvent.click(screen.getByRole('radio', { name: /correction requise/i }));
    await userEvent.click(screen.getByTestId('submit-review'));
    expect(await screen.findByTestId('review-error')).toHaveTextContent(/10 caractères/i);
  });
});

describe('NewDossierPage validation', () => {
  it('blocks creation without a title and shows an error', async () => {
    signIn(analyst);
    renderPage(<NewDossierPage />);
    await userEvent.click(screen.getByRole('button', { name: /créer le dossier/i }));
    expect(await screen.findByTestId('title-error')).toHaveTextContent(/obligatoire/i);
  });
});

describe('AgentsPage (NLU-to-SQL safety UI)', () => {
  it('blocks a dangerous query and shows the read-only message', async () => {
    signIn(analyst);
    renderPage(<AgentsPage />);
    await userEvent.type(screen.getByLabelText(/requête de données/i), 'DROP TABLE dossiers');
    await userEvent.click(screen.getByRole('button', { name: /tester la requête/i }));
    expect(await screen.findByTestId('query-result')).toHaveTextContent(/lecture seule/i);
  });
});

describe('Sidebar navigation and role-based UI', () => {
  it('shows analyst navigation without expert/admin sections', () => {
    signIn(analyst);
    renderPage(<Sidebar />);
    const nav = screen.getByTestId('sidebar');
    expect(within(nav).getByRole('link', { name: /tableau de bord/i })).toHaveAttribute(
      'href',
      '/app/dashboard',
    );
    expect(within(nav).getByRole('link', { name: /dossiers/i })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /revue experte/i })).not.toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /journal d’audit/i })).not.toBeInTheDocument();
  });

  it('shows the expert-review entry for expert users', () => {
    signIn(expert);
    renderPage(<Sidebar />);
    expect(screen.getByRole('link', { name: /revue experte/i })).toBeInTheDocument();
  });

  it('RequireRole renders an unauthorized state instead of the content', () => {
    signIn(analyst);
    renderPage(
      <RequireRole minimum="admin">
        <p>Secret admin</p>
      </RequireRole>,
    );
    expect(screen.getByTestId('unauthorized')).toBeInTheDocument();
    expect(screen.queryByText('Secret admin')).not.toBeInTheDocument();
  });
});
