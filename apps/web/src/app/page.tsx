import React from "react";

export default function QueuePage() {
  return (
    <div className="flex min-h-screen bg-paper">
      {/* Persistent Left Rail (220px) per E.5 */}
      <aside className="w-55 bg-surface border-r border-line p-4 flex flex-col justify-between">
        <div>
          <div className="font-heading font-semibold text-ink text-panel-title tracking-tight mb-6">
            AVENEL
          </div>
          <nav className="flex flex-col space-y-2 text-table-body font-medium">
            <a href="#" className="text-sky-ink font-semibold">
              Dossiers
            </a>
            <a href="#" className="text-ink-2 hover:text-ink">
              Sociétés
            </a>
            <a href="#" className="text-ink-2 hover:text-ink flex items-center justify-between">
              <span>Validations</span>
              <span className="text-pink-ink font-semibold">0</span>
            </a>
            <a href="#" className="text-ink-2 hover:text-ink">
              Paramètres
            </a>
          </nav>
        </div>
        <div className="text-table-meta text-ink-2">
          Cabinet Démo SARL
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-6">
        <header className="flex justify-between items-center mb-6">
          <h1 className="text-page-title text-ink font-heading">
            Dossiers mensuels
          </h1>
          <button className="btn-primary text-table-body">
            Nouveau dossier
          </button>
        </header>

        {/* Empty State per E.8 */}
        <div className="border border-line rounded-panel p-8 text-center bg-surface">
          <p className="text-table-body text-ink-2 mb-4">
            Aucun dossier pour ce mois. Créez un dossier pour commencer.
          </p>
        </div>
      </main>
    </div>
  );
}
