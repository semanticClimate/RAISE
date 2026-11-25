import type React from 'react';
import { useEffect, useState } from 'react';
import type { ChatSession } from '../../types';

export interface SettingsDataControlTabProps {
  sessions: ChatSession[];
  onSessionsChange: (updatedSessions: ChatSession[]) => void;
  onDeleteAllChats: () => void;
  onCloseSettings?: () => void;
}

export const SettingsDataControlTab: React.FC<SettingsDataControlTabProps> = ({
  sessions,
  onSessionsChange,
  onDeleteAllChats,
}) => {
  // Modal states for the actions
  const [isDeleteAllOpen, setIsDeleteAllOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);

  // Persistence on reload toggle (default: false as requested by specification)
  const [persistOnReload, setPersistOnReload] = useState<boolean>(() => {
    try {
      return localStorage.getItem('raise_persist_session_on_reload') === 'true';
    } catch {
      return false;
    }
  });

  const handleTogglePersistOnReload = () => {
    const nextVal = !persistOnReload;
    setPersistOnReload(nextVal);
    try {
      localStorage.setItem('raise_persist_session_on_reload', String(nextVal));
    } catch {}
    showToast(
      nextVal
        ? 'Active session will be restored on page reload'
        : 'Page reload will now start with a clean search page'
    );
  };

  // Toast / feedback notifications
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'json' | 'markdown'>('json');

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  // ESC key listener to close any open sub-popup
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isDeleteAllOpen) setIsDeleteAllOpen(false);
        else if (isExportOpen) setIsExportOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDeleteAllOpen, isExportOpen]);

  // Handler: Delete all chats permanently
  const handleConfirmDeleteAll = () => {
    onDeleteAllChats();
    onSessionsChange([]);

    setIsDeleteAllOpen(false);
    showToast('All chat conversations permanently deleted');
  };

  // Handler: Export data to downloadable file
  const handlePerformExport = () => {
    const exportPayload = {
      version: '1.0.0',
      exportedAt: new Date().toISOString(),
      activeSessions: sessions,
      settings: {
        theme: localStorage.getItem('raise_theme_mode') || 'dark',
        gatewayUrl: localStorage.getItem('raise_gateway_url') || '',
        voice: localStorage.getItem('raise_preferred_voice') || '',
        gridConfig: (() => {
          try {
            const rawGrid = localStorage.getItem('raise_grid_config');
            return rawGrid ? JSON.parse(rawGrid) : null;
          } catch {
            return null;
          }
        })(),
      },
    };

    let blob: Blob;
    let filename: string;

    if (exportFormat === 'json') {
      blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
      filename = `raise-export-${new Date().toISOString().split('T')[0]}.json`;
    } else {
      let md = `# RAISE Chat Conversations Export\nExported: ${new Date().toLocaleString()}\n\n`;
      sessions.forEach((s, idx) => {
        md += `## ${idx + 1}. ${s.title}\n*Timestamp: ${s.timestamp}*\n\n`;
        s.messages.forEach((m) => {
          md += `### ${m.role === 'user' ? 'User' : 'RAISE Assistant'}\n${m.text}\n\n`;
        });
        md += `---\n\n`;
      });
      blob = new Blob([md], { type: 'text/markdown' });
      filename = `raise-transcripts-${new Date().toISOString().split('T')[0]}.md`;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    setIsExportOpen(false);
    showToast(`Exported ${sessions.length} conversations (${exportFormat.toUpperCase()})`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-[150] pointer-events-none animate-in fade-in zoom-in-95 duration-150">
          <div className="px-4 py-2 rounded-xl bg-white/95 dark:bg-[#171717]/95 text-slate-900 dark:text-[#FFFFFF] text-xs font-medium shadow-2xl backdrop-blur-md flex items-center gap-2 border border-slate-200/90 dark:border-[#292929]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <span>{toastMessage}</span>
          </div>
        </div>
      )}

      {/* Header section */}
      <div>
        <h3 className="text-base font-semibold text-slate-900 dark:text-[#FFFFFF]">Data Control</h3>
        <p className="text-xs text-slate-500 dark:text-[#A3A3A3] mt-1">
          Manage your session persistence, export options, and conversation history.
        </p>
      </div>

      {/* Data Control Options */}
      <div className="divide-y divide-slate-200/80 dark:divide-[#292929] rounded-2xl border border-slate-200/80 dark:border-[#292929] bg-slate-50/50 dark:bg-[#0A0A0A] overflow-hidden">
        {/* Toggle: Restore chat on reload */}
        <div className="p-3.5 sm:p-4.5 flex flex-row items-center justify-between gap-3 hover:bg-slate-50 dark:hover:bg-[#111111] transition-colors">
          <div className="space-y-0.5 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-slate-900 dark:text-[#FFFFFF]">
                Restore last active chat on page reload
              </h4>
              <span
                className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${
                  persistOnReload
                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                    : 'bg-slate-200/70 dark:bg-[#171717] border dark:border-[#292929] text-slate-600 dark:text-[#A3A3A3]'
                }`}
              >
                {persistOnReload ? 'Enabled' : 'Fresh Start'}
              </span>
            </div>
            <p className="hidden sm:block text-xs text-slate-500 dark:text-[#A3A3A3]">
              When disabled, refreshing the browser (F5) starts with a clean query landing page while keeping your chat history safely in the sidebar.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={persistOnReload}
            onClick={handleTogglePersistOnReload}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              persistOnReload ? 'bg-[#FFFFFF]' : 'bg-slate-300 dark:bg-[#292929]'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full shadow-lg ring-0 transition duration-200 ease-in-out ${
                persistOnReload ? 'translate-x-5 bg-[#000000]' : 'translate-x-0 bg-white dark:bg-[#A3A3A3]'
              }`}
            />
          </button>
        </div>

        {/* Delete all chats */}
        <div className="p-3.5 sm:p-4.5 flex flex-row items-center justify-between gap-3 hover:bg-rose-50/40 dark:hover:bg-rose-500/5 transition-colors">
          <div className="space-y-0.5 min-w-0">
            <h4 className="text-sm font-semibold text-rose-600 dark:text-rose-400">
              Delete all chats
            </h4>
            <p className="hidden sm:block text-xs text-slate-500 dark:text-[#A3A3A3]">
              Permanently erase all chat conversations, prompt histories, and source attachments from this browser.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsDeleteAllOpen(true)}
            className="px-3.5 sm:px-4 py-1.5 sm:py-2 rounded-xl text-xs font-semibold text-rose-600 hover:text-white dark:text-rose-400 dark:hover:text-white bg-rose-50 hover:bg-rose-600 dark:bg-rose-500/10 dark:hover:bg-rose-600 border border-rose-200 dark:border-rose-500/30 transition-all shadow-2xs active:scale-98 cursor-pointer shrink-0"
          >
            Delete all
          </button>
        </div>

        {/* Export data */}
        <div className="p-3.5 sm:p-4.5 flex flex-row items-center justify-between gap-3 hover:bg-slate-50 dark:hover:bg-[#111111] transition-colors">
          <div className="space-y-0.5 min-w-0">
            <h4 className="text-sm font-semibold text-slate-900 dark:text-[#FFFFFF]">Export data</h4>
            <p className="hidden sm:block text-xs text-slate-500 dark:text-[#A3A3A3]">
              Download an export of your chats, library document manifests, and custom configuration settings.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsExportOpen(true)}
            className="px-3.5 sm:px-4 py-1.5 sm:py-2 rounded-xl text-xs font-semibold bg-white dark:bg-[#171717] hover:bg-slate-100 dark:hover:bg-[#292929] text-slate-800 dark:text-[#FFFFFF] border border-slate-200/90 dark:border-[#292929] transition-all shadow-2xs active:scale-98 cursor-pointer shrink-0"
          >
            Export
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          POPUP: DELETE ALL CHATS CONFIRMATION POPUP
          (Clicking outside the popup closes the delete all popup)
         ───────────────────────────────────────────────────────────── */}
      {isDeleteAllOpen && (
        <div
          id="deleteAllModalBackdrop"
          className="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setIsDeleteAllOpen(false);
            }
          }}
        >
          <div
            id="deleteAllModalDialog"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-white dark:bg-[#0A0A0A] border border-rose-200 dark:border-rose-500/30 rounded-2xl shadow-2xl p-5 select-none space-y-4 animate-in zoom-in-95 duration-150"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-100 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400 flex items-center justify-center shrink-0">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-slate-900 dark:text-[#FFFFFF]">
                  Delete all chats?
                </h3>
                <p className="text-xs text-slate-500 dark:text-[#A3A3A3] leading-relaxed">
                  Are you sure you want to permanently delete all{' '}
                  <strong className="text-rose-600 dark:text-rose-400">{sessions.length}</strong>{' '}
                  chat conversations? All message history, questions, and attached documents in this
                  browser will be wiped. This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200/80 dark:border-[#292929]">
              <button
                type="button"
                onClick={() => setIsDeleteAllOpen(false)}
                className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 dark:text-[#A3A3A3] hover:bg-slate-100 dark:hover:bg-[#171717] rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteAll}
                className="px-4 py-1.5 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-xl transition-colors cursor-pointer shadow-xs active:scale-95"
              >
                Delete all chats
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          POPUP: EXPORT DATA POPUP
         ───────────────────────────────────────────────────────────── */}
      {isExportOpen && (
        <div
          id="exportModalBackdrop"
          className="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsExportOpen(false);
          }}
        >
          <div
            id="exportModalDialog"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-white dark:bg-[#0A0A0A] border border-slate-200 dark:border-[#292929] rounded-2xl shadow-2xl p-5 select-none space-y-4 animate-in zoom-in-95 duration-150"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-[#171717] text-slate-900 dark:text-[#FFFFFF] border dark:border-[#292929] flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-[#FFFFFF]">
                  Export data
                </h3>
                <p className="text-xs text-slate-500 dark:text-[#A3A3A3] leading-relaxed">
                  Export all your conversations and configuration settings for backup or analysis.
                </p>
              </div>
            </div>

            {/* Export Summary Card */}
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#111111] border border-slate-200/80 dark:border-[#292929] flex items-center justify-between">
              <div>
                <span className="text-slate-500 dark:text-[#A3A3A3] text-xs">Total Conversations</span>
                <p className="font-semibold text-slate-900 dark:text-[#FFFFFF] text-base mt-0.5">
                  {sessions.length} {sessions.length === 1 ? 'chat' : 'chats'}
                </p>
              </div>
              <span className="text-[11px] font-mono text-slate-400 dark:text-[#A3A3A3]">
                {exportFormat.toUpperCase()} format
              </span>
            </div>

            {/* Format selection */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-800 dark:text-[#FFFFFF]">
                Export Format
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setExportFormat('json')}
                  className={`p-2.5 rounded-xl text-left border transition-all cursor-pointer ${
                    exportFormat === 'json'
                      ? 'border-[#FFFFFF] bg-slate-100 dark:bg-[#171717] text-slate-900 dark:text-[#FFFFFF]'
                      : 'border-slate-200 dark:border-[#292929] text-slate-700 dark:text-[#A3A3A3] hover:border-slate-300 dark:hover:border-[#383838]'
                  }`}
                >
                  <span className="text-xs font-semibold block">JSON Data</span>
                  <span className="text-[10px] text-slate-500 dark:text-[#A3A3A3]">
                    Complete structure
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setExportFormat('markdown')}
                  className={`p-2.5 rounded-xl text-left border transition-all cursor-pointer ${
                    exportFormat === 'markdown'
                      ? 'border-[#FFFFFF] bg-slate-100 dark:bg-[#171717] text-slate-900 dark:text-[#FFFFFF]'
                      : 'border-slate-200 dark:border-[#292929] text-slate-700 dark:text-[#A3A3A3] hover:border-slate-300 dark:hover:border-[#383838]'
                  }`}
                >
                  <span className="text-xs font-semibold block">Markdown</span>
                  <span className="text-[10px] text-slate-500 dark:text-[#A3A3A3]">
                    Readable text
                  </span>
                </button>
              </div>
            </div>

            {/* Footer buttons */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200/80 dark:border-[#292929]">
              <button
                type="button"
                onClick={() => setIsExportOpen(false)}
                className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 dark:text-[#A3A3A3] hover:bg-slate-100 dark:hover:bg-[#171717] rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePerformExport}
                className="px-4 py-1.5 text-xs font-semibold bg-[#FFFFFF] hover:bg-slate-200 text-[#000000] rounded-xl transition-colors cursor-pointer"
              >
                Download Export
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
