import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import type { Report } from '@/types/models';
import { reportService } from '@/services/reportService';
import { useCurrentUser } from '@/store/authStore';
import { toast } from '@/store/toastStore';
import { ReportPreview } from '@/components/domain/ReportPreview';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonCard } from '@/components/ui/Skeleton';

export function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const user = useCurrentUser();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [exporting, setExporting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!user || !id) return;
    let cancelled = false;
    setError(null);
    reportService
      .get(user.organizationId, id)
      .then((r) => !cancelled && setReport(r))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [user, id, reloadKey]);

  async function handleExport() {
    if (!user || !id) return;
    setExporting(true);
    try {
      const text = await reportService.exportText({ user }, id);
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fiscai-rapport-${id}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      toast('success', 'Rapport exporté.');
    } catch (e) {
      toast('error', e instanceof Error ? e.message : 'Export impossible.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Link
          to="/app/reports"
          className="inline-flex items-center gap-1 text-sm text-brand-700 underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Tous les rapports
        </Link>
        {report && (
          <button
            type="button"
            className="btn-primary"
            onClick={() => void handleExport()}
            disabled={exporting}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {exporting ? 'Export…' : 'Exporter (texte)'}
          </button>
        )}
      </div>
      {error ? (
        <ErrorState
          error={error}
          title="Rapport introuvable"
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      ) : !report ? (
        <div aria-busy="true">
          <SkeletonCard />
        </div>
      ) : (
        <ReportPreview report={report} />
      )}
    </div>
  );
}
