import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { Modal } from './Modal';
import { Pagination } from './Pagination';
import { SkeletonCard } from './Skeleton';
import { ServiceError } from '@/services/db';

describe('EmptyState', () => {
  it('renders title, description and action', () => {
    render(
      <EmptyState
        title="Aucun dossier"
        description="Créez-en un."
        action={<button>Créer</button>}
      />,
    );
    const state = screen.getByTestId('empty-state');
    expect(state).toHaveTextContent('Aucun dossier');
    expect(state).toHaveTextContent('Créez-en un.');
    expect(screen.getByRole('button', { name: 'Créer' })).toBeInTheDocument();
  });
});

describe('ErrorState', () => {
  it('shows the message, suggested action, and a retry button', async () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        error={new ServiceError('X', 'Panne réseau.', 'Vérifiez votre connexion.')}
        onRetry={onRetry}
      />,
    );
    const state = screen.getByTestId('error-state');
    expect(state).toHaveTextContent('Panne réseau.');
    expect(state).toHaveTextContent('Vérifiez votre connexion.');
    await userEvent.click(screen.getByRole('button', { name: /réessayer/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe('Modal', () => {
  it('renders when open, closes on Escape, and traps a dialog role', async () => {
    const onClose = vi.fn();
    render(
      <Modal open title="Confirmer" onClose={onClose}>
        <p>Contenu</p>
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Confirmer' })).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('renders nothing when closed', () => {
    render(
      <Modal open={false} title="Caché" onClose={() => {}}>
        <p>Rien</p>
      </Modal>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Pagination', () => {
  it('navigates between pages and disables bounds', async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} pageSize={10} total={25} onPageChange={onPageChange} />);
    expect(screen.getByText(/page 1 sur 3/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /page précédente/i })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: /page suivante/i }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('renders nothing for a single page', () => {
    const { container } = render(
      <Pagination page={1} pageSize={10} total={5} onPageChange={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe('SkeletonCard', () => {
  it('marks itself as busy for assistive tech', () => {
    render(<SkeletonCard />);
    expect(screen.getByTestId('skeleton-card')).toHaveAttribute('aria-busy', 'true');
  });
});
