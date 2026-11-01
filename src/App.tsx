import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { RequireAuth, RequireRole } from '@/components/layout/guards';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { Spinner } from '@/components/ui/Spinner';
import { LandingPage } from '@/pages/LandingPage';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';

// Heavy pages are lazy-loaded for performance.
const RegisterPage = lazy(() =>
  import('@/pages/RegisterPage').then((m) => ({ default: m.RegisterPage })),
);
const PricingPage = lazy(() =>
  import('@/pages/PricingPage').then((m) => ({ default: m.PricingPage })),
);
const DossiersPage = lazy(() =>
  import('@/pages/DossiersPage').then((m) => ({ default: m.DossiersPage })),
);
const NewDossierPage = lazy(() =>
  import('@/pages/NewDossierPage').then((m) => ({ default: m.NewDossierPage })),
);
const DossierDetailPage = lazy(() =>
  import('@/pages/DossierDetailPage').then((m) => ({ default: m.DossierDetailPage })),
);
const DocumentsPage = lazy(() =>
  import('@/pages/DocumentsPage').then((m) => ({ default: m.DocumentsPage })),
);
const DocumentReviewPage = lazy(() =>
  import('@/pages/DocumentReviewPage').then((m) => ({ default: m.DocumentReviewPage })),
);
const AgentsPage = lazy(() =>
  import('@/pages/AgentsPage').then((m) => ({ default: m.AgentsPage })),
);
const AlertsPage = lazy(() =>
  import('@/pages/AlertsPage').then((m) => ({ default: m.AlertsPage })),
);
const ExpertReviewPage = lazy(() =>
  import('@/pages/ExpertReviewPage').then((m) => ({ default: m.ExpertReviewPage })),
);
const ReportsPage = lazy(() =>
  import('@/pages/ReportsPage').then((m) => ({ default: m.ReportsPage })),
);
const ReportDetailPage = lazy(() =>
  import('@/pages/ReportDetailPage').then((m) => ({ default: m.ReportDetailPage })),
);
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
const AuditLogPage = lazy(() =>
  import('@/pages/AuditLogPage').then((m) => ({ default: m.AuditLogPage })),
);
const PilotDemoPage = lazy(() =>
  import('@/pages/PilotDemoPage').then((m) => ({ default: m.PilotDemoPage })),
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
);

function PageFallback() {
  return (
    <div className="flex min-h-40 items-center justify-center">
      <Spinner label="Chargement de la page…" />
    </div>
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/viewer" element={<DocumentReviewPage />} />
            <Route path="/pilot" element={<PilotDemoPage />} />
            <Route
              path="/app"
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route index element={<Navigate to="/app/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="dossiers" element={<DossiersPage />} />
              <Route path="dossiers/new" element={<NewDossierPage />} />
              <Route path="dossiers/:id" element={<DossierDetailPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="documents/:id/review" element={<DocumentReviewPage />} />
              <Route path="agents" element={<AgentsPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route
                path="expert-review"
                element={
                  <RequireRole minimum="expert">
                    <ExpertReviewPage />
                  </RequireRole>
                }
              />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="reports/:id" element={<ReportDetailPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route
                path="audit"
                element={
                  <RequireRole minimum="admin">
                    <AuditLogPage />
                  </RequireRole>
                }
              />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
