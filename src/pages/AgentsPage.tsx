import { useState } from 'react';
import { Lock } from 'lucide-react';
import { AGENT_PIPELINE, aiAnalysisService } from '@/services/aiAnalysisService';
import { useCurrentUser } from '@/store/authStore';
import { READ_ONLY_MESSAGE } from '@/lib/sqlGuard';
import { AgentCard } from '@/components/domain/AgentCard';
import { Disclaimer } from '@/components/domain/Disclaimer';
import type { AgentRun } from '@/types/models';

const IDLE_RUNS: AgentRun[] = AGENT_PIPELINE.map((step) => ({
  agentId: step.agentId,
  agentName: step.agentName,
  description: step.description,
  status: 'idle',
  confidence: 0,
  findings: [],
  evidence: [],
  recommendedAction: 'Lancez une analyse depuis un dossier pour activer cet agent.',
}));

export function AgentsPage() {
  const user = useCurrentUser();
  const [query, setQuery] = useState('');
  const [queryResult, setQueryResult] = useState<{ blocked: boolean; message: string } | null>(
    null,
  );
  const [running, setRunning] = useState(false);

  async function handleQuery() {
    if (!user || !query.trim()) return;
    setRunning(true);
    try {
      setQueryResult(await aiAnalysisService.queryData({ user }, query));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Agents IA</h1>
        <p className="text-sm text-slate-500">
          Le pipeline agentique FiscAI : chaque agent est spécialisé, journalisé, et soumis à
          validation humaine pour les cas à risque.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2" data-testid="agent-pipeline">
        {IDLE_RUNS.map((run) => (
          <AgentCard key={run.agentId} run={run} />
        ))}
      </div>

      <section aria-label="Agent de requêtes de données" className="card p-6">
        <div className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-brand-600" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-slate-900">
            Agent Requêtes de données (aperçu)
          </h2>
        </div>
        <p className="mt-1 text-sm text-slate-500">{READ_ONLY_MESSAGE}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <label htmlFor="data-query" className="sr-only">
            Requête de données
          </label>
          <input
            id="data-query"
            className="input flex-1"
            placeholder="Ex. SELECT * FROM dossiers WHERE statut = 'needs_review'"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary"
            onClick={() => void handleQuery()}
            disabled={running || !query.trim()}
          >
            {running ? 'Vérification…' : 'Tester la requête'}
          </button>
        </div>
        {queryResult && (
          <p
            role="status"
            data-testid="query-result"
            className={`mt-3 rounded-lg p-3 text-sm ${
              queryResult.blocked ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'
            }`}
          >
            {queryResult.message}
          </p>
        )}
      </section>

      <Disclaimer />
    </div>
  );
}
