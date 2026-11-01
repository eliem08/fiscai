import React, { useState } from 'react';
import { Plus, ChevronDown, AlertCircle } from 'lucide-react';

export interface QueueRowItem {
  id: string;
  client_id: string;
  company_name: string;
  period_code: string;
  documents_count: number;
  status: 'draft' | 'intake' | 'reviewing' | 'awaiting_approval' | 'approved' | 'exporting' | 'completed';
  status_label: string;
  issues_count: number;
  blocking_issues_count: number;
  due_date: string;
  assigned_to?: string | null;
  needs_person: boolean;
}

export interface QueueScreenProps {
  items: QueueRowItem[];
  selectedMonth?: string;
  onSelectMonth?: (month: string) => void;
  onSelectRow?: (item: QueueRowItem) => void;
  onNewDossier?: () => void;
  isLoading?: boolean;
}

export const QueueScreen: React.FC<QueueScreenProps> = ({
  items,
  selectedMonth = 'Septembre 2026',
  onSelectMonth,
  onSelectRow,
  onNewDossier,
  isLoading = false,
}) => {
  const [selectedRowId, setSelectedRowId] = useState<string | null>(items[0]?.id || null);

  return (
    <div className="flex flex-col h-full bg-slate-50 text-slate-900" data-testid="queue-screen">
      {/* Top Bar with Month Selector and Action Button */}
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200">
        <div className="flex items-center space-x-2">
          <label htmlFor="month-selector" className="sr-only">
            Sélectionner le mois
          </label>
          <div className="relative inline-flex items-center">
            <select
              id="month-selector"
              value={selectedMonth}
              onChange={(e) => onSelectMonth?.(e.target.value)}
              className="appearance-none font-semibold text-lg text-slate-900 bg-transparent pr-7 py-1 focus:outline-none focus:ring-1 focus:ring-brand-500 rounded cursor-pointer"
            >
              <option value="Septembre 2026">Septembre 2026</option>
              <option value="Octobre 2026">Octobre 2026</option>
              <option value="Novembre 2026">Novembre 2026</option>
            </select>
            <ChevronDown className="w-4 h-4 text-slate-500 absolute right-1 pointer-events-none" aria-hidden="true" />
          </div>
        </div>

        <button
          type="button"
          onClick={onNewDossier}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded shadow-sm transition-colors"
          data-testid="new-dossier-btn"
        >
          <Plus className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Nouveau dossier</span>
        </button>
      </header>

      {/* Content Area */}
      <main className="flex-1 p-6 overflow-auto">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500 text-sm" role="status">
            Chargement de la file d'attente…
          </div>
        ) : items.length === 0 ? (
          <div className="bg-white rounded-lg border border-slate-200 p-12 text-center shadow-sm">
            <p className="text-sm text-slate-600" data-testid="empty-queue-message">
              Aucun dossier pour septembre. Créez un dossier pour commencer.
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-left border-collapse text-xs" aria-label="File d'attente des dossiers mensuels">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider">
                  <th scope="col" className="py-3 px-4 w-64">Société</th>
                  <th scope="col" className="py-3 px-3 w-24 text-right">Pièces</th>
                  <th scope="col" className="py-3 px-4 w-32">État</th>
                  <th scope="col" className="py-3 px-3 w-28 text-center">Anomalies</th>
                  <th scope="col" className="py-3 px-4 w-28">Échéance</th>
                  <th scope="col" className="py-3 px-4 w-36">Assigné</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((row) => {
                  const isSelected = row.id === selectedRowId;
                  return (
                    <tr
                      key={row.id}
                      onClick={() => {
                        setSelectedRowId(row.id);
                        onSelectRow?.(row);
                      }}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          setSelectedRowId(row.id);
                          onSelectRow?.(row);
                        }
                      }}
                      className={`cursor-pointer transition-colors relative ${
                        row.needs_person
                          ? 'border-l-4 border-l-[#D93874] bg-[#FFF0F5]/30'
                          : isSelected
                          ? 'bg-slate-50 border-l-4 border-l-indigo-600'
                          : 'hover:bg-slate-50 border-l-4 border-l-transparent'
                      }`}
                      data-testid={`queue-row-${row.id}`}
                    >
                      <td className="py-3 px-4 font-semibold text-slate-900">
                        <div className="flex items-center gap-2">
                          <span>{row.company_name}</span>
                          {row.needs_person && (
                            <span
                              className="w-1.5 h-1.5 rounded-full bg-[#D93874]"
                              title="À traiter par une personne"
                              role="img"
                              aria-label="En attente d'une personne"
                            />
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-mono tabular-nums text-slate-700">
                        {row.documents_count}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                            row.status === 'awaiting_approval'
                              ? 'bg-[#FFF0F5] text-[#9E1B4C] border border-[#F4B4C8]'
                              : row.status === 'approved'
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {row.status_label}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        {row.issues_count > 0 ? (
                          <span className="inline-flex items-center gap-1 font-mono text-slate-900 font-semibold">
                            {row.blocking_issues_count > 0 && (
                              <AlertCircle className="w-3.5 h-3.5 text-[#D93874]" aria-hidden="true" />
                            )}
                            <span>{row.issues_count}</span>
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-600">
                        {row.due_date}
                      </td>
                      <td className="py-3 px-4 text-slate-700">
                        {row.assigned_to || <span className="text-slate-600">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
};
