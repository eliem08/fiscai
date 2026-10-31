import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { RiskBadge } from './RiskBadge';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { KpiCard } from './KpiCard';
import { DossierCard } from './DossierCard';
import { AlertCard } from './AlertCard';
import { UploadZone } from './UploadZone';
import { AgentCard } from './AgentCard';
import { ReportPreview } from './ReportPreview';
import { ChecklistView } from './ChecklistView';
import { Disclaimer } from './Disclaimer';
import { buildReport, REQUIRED_REPORT_SECTIONS } from '@/lib/report';
import { computeRiskScores } from '@/lib/riskScoring';
import { buildChecklist } from '@/lib/checklist';
import { seedDossiers, seedOrganizations, seedAlerts } from '@/mocks/seed';
import type { AgentRun, AnalysisResult } from '@/types/models';

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('RiskBadge', () => {
  it.each([
    ['low', 'Risque faible'],
    ['medium', 'Risque moyen'],
    ['high', 'Risque élevé'],
    ['critical', 'Risque critique'],
  ] as const)('shows the %s level with a text label (no color-only meaning)', (level, label) => {
    render(<RiskBadge level={level} score={42} />);
    const badge = screen.getByTestId('risk-badge');
    expect(badge).toHaveAttribute('data-level', level);
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveTextContent('42/100');
  });
});

describe('SeverityBadge', () => {
  it('renders severity with a textual label', () => {
    render(<SeverityBadge severity="critical" />);
    expect(screen.getByTestId('severity-badge')).toHaveTextContent('Critique');
  });
});

describe('StatusBadge / DossierCard', () => {
  it('displays the dossier status correctly', () => {
    renderWithRouter(<DossierCard dossier={seedDossiers[0]} />);
    const card = screen.getByTestId('dossier-card');
    expect(card).toHaveTextContent('Import composants électroniques — Shenzhen');
    expect(card).toHaveTextContent('ElectroMaroc SARL');
    expect(within(card).getByTestId('status-badge')).toHaveTextContent('Revue requise');
    expect(card).toHaveAttribute('href', '/app/dossiers/dos_001');
  });

  it('renders each status with its French label', () => {
    render(<StatusBadge status="issue" />);
    expect(screen.getByTestId('status-badge')).toHaveTextContent('Problème actif');
  });
});

describe('KpiCard', () => {
  it('displays the label, value and hint', () => {
    render(<KpiCard label="Dossiers actifs" value={12} hint="Tous types" />);
    expect(screen.getByTestId('kpi-card')).toHaveTextContent('Dossiers actifs');
    expect(screen.getByTestId('kpi-value')).toHaveTextContent('12');
    expect(screen.getByTestId('kpi-card')).toHaveTextContent('Tous types');
  });
});

describe('AlertCard', () => {
  it('displays severity, detail and status actions', async () => {
    const onChange = vi.fn();
    renderWithRouter(<AlertCard alert={seedAlerts[0]} onStatusChange={onChange} />);
    const card = screen.getByTestId('alert-card');
    expect(card).toHaveAttribute('data-severity', 'critical');
    expect(card).toHaveTextContent('Liste de colisage manquante');
    await userEvent.click(screen.getByRole('button', { name: /passer en revue/i }));
    expect(onChange).toHaveBeenCalledWith('in_review');
  });
});

describe('UploadZone', () => {
  it('accepts an allowed file and calls onUpload', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    render(<UploadZone onUpload={onUpload} />);
    const input = screen.getByLabelText(/sélectionner un document/i) as HTMLInputElement;
    const file = new File(['%PDF'], 'facture.pdf', { type: 'application/pdf' });
    await userEvent.upload(input, file);
    expect(onUpload).toHaveBeenCalledOnce();
    expect(onUpload.mock.calls[0][0].name).toBe('facture.pdf');
  });

  it('rejects an invalid file type with a visible error', async () => {
    const onUpload = vi.fn();
    render(<UploadZone onUpload={onUpload} />);
    const input = screen.getByLabelText(/sélectionner un document/i) as HTMLInputElement;
    const file = new File(['MZ'], 'malware.exe', { type: 'application/octet-stream' });
    // userEvent.upload respects the accept attribute, so fire the change directly.
    Object.defineProperty(input, 'files', { value: [file] });
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.change(input);
    expect(onUpload).not.toHaveBeenCalled();
    expect(await screen.findByTestId('upload-error')).toHaveTextContent(/non supporté/i);
  });
});

describe('AgentCard', () => {
  const run: AgentRun = {
    agentId: 'tax',
    agentName: 'Agent Fiscal',
    description: 'Contrôles TVA',
    status: 'needs_review',
    confidence: 0.82,
    findings: ['Incohérence TVA détectée'],
    evidence: ['HT=100, TTC=120'],
    recommendedAction: 'Corriger la facture.',
  };

  it('renders status, confidence, findings, evidence and recommended action', () => {
    render(<AgentCard run={run} />);
    const card = screen.getByTestId('agent-card');
    expect(card).toHaveAttribute('data-status', 'needs_review');
    expect(card).toHaveTextContent('Agent Fiscal');
    expect(card).toHaveTextContent('Revue humaine requise');
    expect(card).toHaveTextContent('82%');
    expect(card).toHaveTextContent('Incohérence TVA détectée');
    expect(card).toHaveTextContent('Corriger la facture.');
  });
});

describe('ReportPreview', () => {
  it('renders every required report section', () => {
    const scores = computeRiskScores({
      dossierType: 'import',
      documentTypes: ['commercial_invoice'],
      extractions: [],
    });
    const analysis: AnalysisResult = {
      id: 'ana_test',
      dossierId: seedDossiers[0].id,
      organizationId: 'org_demo',
      createdAt: new Date().toISOString(),
      scores,
      extractions: [],
      checklist: buildChecklist({
        dossierType: 'import',
        documentTypes: ['commercial_invoice'],
        scores,
      }),
      agentRuns: [],
      supplierQuestions: [],
      lowConfidence: false,
      partial: true,
    };
    const report = buildReport(
      seedOrganizations[0],
      seedDossiers[0],
      analysis,
      'pending',
      'Résumé audit.',
    );
    render(<ReportPreview report={report} />);
    const preview = screen.getByTestId('report-preview');
    for (const key of REQUIRED_REPORT_SECTIONS) {
      expect(preview.querySelector(`[data-section="${key}"]`)).not.toBeNull();
    }
    expect(preview).toHaveTextContent('Atlas Import Export SARL');
    expect(preview).toHaveTextContent(/vérifiés par un comptable/);
  });
});

describe('ChecklistView', () => {
  it('renders each check with its status label', () => {
    render(
      <ChecklistView
        items={[
          { id: '1', label: 'Facture commerciale', status: 'passed', detail: 'ok' },
          {
            id: '2',
            label: 'Liste de colisage',
            status: 'missing',
            detail: 'absente',
            recommendedAction: 'Ajouter',
          },
        ]}
      />,
    );
    const list = screen.getByTestId('checklist');
    expect(list).toHaveTextContent('Conforme');
    expect(list).toHaveTextContent('Manquant');
    expect(list).toHaveTextContent('Ajouter');
  });
});

describe('Disclaimer', () => {
  it('shows the mandatory legal disclaimer text', () => {
    render(<Disclaimer />);
    expect(screen.getByTestId('legal-disclaimer')).toHaveTextContent(
      /assistance au pré-contrôle fiscal et douanier/,
    );
  });
});
