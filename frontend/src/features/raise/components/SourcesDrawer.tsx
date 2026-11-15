import React, { useState } from 'react';
import { ExtractedDocumentModal } from '../../../components/library/ExtractedDocumentModal';
import { useModeStore } from '../../../stores/modeStore';
import type { SourceDocument } from '../../../types';
import { SourceDocItem } from './SourceDocItem';
import { SourcesDrawerAddMenu } from './SourcesDrawerAddMenu';

export interface SourcesDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sourceDocs: SourceDocument[];
  activeSourcesCount: number;
  sourceFilter: string;
  setSourceFilter: (filter: string) => void;
  addSourceMenuOpen: 'drawer' | 'input' | null;
  setAddSourceMenuOpen: React.Dispatch<React.SetStateAction<'drawer' | 'input' | null>>;
  onBrowseFileClick: () => void;
  onOpenLibraryPicker: () => void;
  isDocReady: (doc: SourceDocument) => boolean;
  onToggleSourceDoc: (id: string) => void;
  onToggleAllSources?: (select: boolean) => void;
  onDeleteSourceDoc: (id: string, name: string) => void;
  onViewPdf?: (filename: string, pageNumber?: number) => void;
}

export const SourcesDrawer: React.FC<SourcesDrawerProps> = ({
  isOpen,
  onClose,
  sourceDocs,
  activeSourcesCount,
  sourceFilter,
  setSourceFilter,
  addSourceMenuOpen,
  setAddSourceMenuOpen,
  onBrowseFileClick,
  onOpenLibraryPicker,
  isDocReady,
  onToggleSourceDoc,
  onToggleAllSources,
  onDeleteSourceDoc,
  onViewPdf,
}) => {
  const { appMode } = useModeStore();
  const isOnline = appMode === 'connected' || appMode === 'degraded';

  const [artifactModal, setArtifactModal] = useState<{
    isOpen: boolean;
    documentName: string;
    type: 'markdown' | 'okf';
    url?: string;
  }>({
    isOpen: false,
    documentName: '',
    type: 'markdown',
  });

  if (!isOpen) return null;

  const allSelected = sourceDocs.length > 0 && sourceDocs.every((d) => d.selected);
  const filteredDocs = sourceDocs.filter((d) =>
    d.name.toLowerCase().includes(sourceFilter.toLowerCase())
  );

  return (
    <div
      id="sourcesModalBackdrop"
      className="fixed inset-0 z-[110] flex items-center justify-center p-[clamp(0.5rem,2.5vw,1.25rem)] bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        id="sourcesModalDialog"
        role="dialog"
        aria-modal="true"
        aria-label="Source Documents Drawer"
        onClick={(e) => e.stopPropagation()}
        className="w-[min(96vw,44rem)] max-w-2xl h-auto max-h-[min(88dvh,560px)] min-h-0 bg-white dark:bg-[#181b26] text-slate-900 dark:text-slate-100 border border-slate-300/90 dark:border-white/15 rounded-2xl sm:rounded-3xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150 select-none transition-all duration-200"
      >
        {/* Modal Header */}
        <div className="p-[clamp(0.625rem,2vw,1rem)] border-b border-slate-200/90 dark:border-white/10 flex flex-col bg-slate-50/80 dark:bg-white/[0.02] shrink-0">
          <div className="w-10 h-1 rounded-full bg-slate-300 dark:bg-white/20 mx-auto -mt-0.5 mb-2.5 sm:hidden" />

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center text-indigo-600 dark:text-[#a8c7fa] shrink-0 shadow-2xs">
                <svg
                  className="w-4 h-4 sm:w-4.5 sm:h-4.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
                  />
                </svg>
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm sm:base font-semibold text-slate-900 dark:text-white truncate">
                    Drawer
                  </h2>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold shrink-0 ${
                      isOnline
                        ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-300 dark:border-indigo-400/30'
                        : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                    }`}
                  >
                    {isOnline ? `${activeSourcesCount} active` : 'Offline'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                  Source data documents for retrieval augmented generation
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                id="closeSourcesBtn"
                type="button"
                onClick={onClose}
                className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-white/10 rounded-xl transition-colors cursor-pointer shrink-0"
                title="Close"
                aria-label="Close drawer popup"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Filter & Actions Bar */}
        <div className="p-2.5 sm:px-4 sm:py-3 border-b border-slate-200/80 dark:border-white/10 bg-slate-50/50 dark:bg-white/[0.01] flex items-center gap-2 sm:gap-2.5 shrink-0">
          <div className="relative flex-1 min-w-0">
            <input
              type="text"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              placeholder="Filter sources by title..."
              className="w-full bg-white dark:bg-white/[0.05] border border-slate-200/90 dark:border-white/10 rounded-xl pl-8 pr-7 py-1.5 text-xs text-slate-900 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-500 transition-all shadow-2xs"
            />
            <svg
              className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 absolute left-2.5 top-2.5 pointer-events-none"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
            </svg>
            {sourceFilter && (
              <button
                type="button"
                onClick={() => setSourceFilter('')}
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 rounded cursor-pointer"
                title="Clear filter"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </div>

          <SourcesDrawerAddMenu
            isOpen={addSourceMenuOpen === 'drawer'}
            onToggle={() => setAddSourceMenuOpen((prev) => (prev === 'drawer' ? null : 'drawer'))}
            onClose={() => setAddSourceMenuOpen(null)}
            onBrowseFileClick={onBrowseFileClick}
            onOpenLibraryPicker={onOpenLibraryPicker}
          />
        </div>

        {/* Scrollable Document List */}
        <div className="p-3 sm:p-4 overflow-y-auto max-h-[340px] space-y-2">
          {sourceDocs.length > 0 && (
            <div className="flex items-center justify-between px-1 py-0.5 text-xs text-slate-500 dark:text-slate-400">
              <span className="text-[11px] font-medium">
                {sourceFilter
                  ? `Showing ${filteredDocs.length} of ${sourceDocs.length}`
                  : `${activeSourcesCount} of ${sourceDocs.length} active`}
              </span>

              {onToggleAllSources && sourceDocs.length > 0 && (
                <button
                  type="button"
                  onClick={() => onToggleAllSources(!allSelected)}
                  className="text-[11px] font-semibold text-indigo-600 dark:text-[#a8c7fa] hover:underline cursor-pointer shrink-0"
                >
                  {allSelected ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>
          )}

          {!isOnline && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-700 dark:text-amber-300 text-xs">
              <div className="w-2 h-2 rounded-full bg-amber-400 shrink-0 animate-pulse" />
              <span>
                Gateway Disconnected: Unable to reach backend document store. Connect your gateway
                in Control Center to sync documents.
              </span>
            </div>
          )}

          {filteredDocs.map((doc) => (
            <SourceDocItem
              key={doc.id}
              doc={doc}
              isReady={isDocReady(doc)}
              onToggle={onToggleSourceDoc}
              onDelete={onDeleteSourceDoc}
              onViewPdf={onViewPdf}
              onOpenArtifactModal={(documentName, type, url) =>
                setArtifactModal({ isOpen: true, documentName, type, url })
              }
            />
          ))}

          {filteredDocs.length === 0 && (
            <div className="text-center py-5 sm:py-7 px-4 rounded-2xl border border-dashed border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-white/[0.01]">
              <div className="w-9 h-9 sm:w-11 sm:h-11 mx-auto mb-2.5 rounded-2xl bg-slate-100 dark:bg-white/5 flex items-center justify-center text-slate-400">
                <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.5"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              </div>
              <p className="text-xs sm:text-sm font-semibold text-slate-900 dark:text-white">
                {!isOnline
                  ? 'Gateway Disconnected'
                  : sourceFilter
                    ? 'No matching sources found'
                    : 'No sources attached yet'}
              </p>
              <p className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                {!isOnline
                  ? 'Connect to your pipeline gateway in Control Center or Settings to view indexed documents.'
                  : sourceFilter
                    ? `No sources match "${sourceFilter}". Try a different keyword.`
                    : 'Click the Add button above to attach documents to this conversation.'}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-2.5 sm:px-4 sm:py-3 border-t border-slate-200 dark:border-white/10 bg-slate-50/80 dark:bg-white/[0.02] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-slate-400'}`}
            />
            <span className="text-[11.5px] font-medium text-slate-600 dark:text-slate-300">
              {isOnline
                ? `${activeSourcesCount} of ${sourceDocs.length} documents attached`
                : 'Gateway offline • 0 active documents'}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100 transition-all shadow-xs active:scale-95 cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>

      {/* Extracted Markdown & OKF Catalog Modal */}
      <ExtractedDocumentModal
        isOpen={artifactModal.isOpen}
        onClose={() => setArtifactModal((prev) => ({ ...prev, isOpen: false }))}
        documentName={artifactModal.documentName}
        type={artifactModal.type}
        url={artifactModal.url}
      />
    </div>
  );
};
