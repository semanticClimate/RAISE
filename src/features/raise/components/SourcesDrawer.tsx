import { Database, Search, X } from 'lucide-react';
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
      className="fixed inset-0 z-[110] flex items-center justify-center p-3 sm:p-5 bg-[#000000]/40 backdrop-blur-md animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        id="sourcesModalDialog"
        role="dialog"
        aria-modal="true"
        aria-label="Source Documents Drawer"
        onClick={(e) => e.stopPropagation()}
        className="w-[min(96vw,44rem)] max-w-2xl h-auto max-h-[min(88dvh,560px)] min-h-0 bg-[#0A0A0A] text-[#FFFFFF] border border-[#292929] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150 select-none font-sans"
      >
        {/* Modal Header */}
        <div className="h-14 px-5 sm:px-6 border-b border-[#292929] bg-[#0A0A0A] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
              <Database className="w-4 h-4 text-[#FFFFFF]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-semibold text-[#FFFFFF] truncate">
                  Drawer
                </h2>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-[#171717] text-[#A3A3A3] border border-[#292929]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF]" />
                  <span>{isOnline ? `${activeSourcesCount} active` : 'Offline'}</span>
                </span>
              </div>
            </div>
          </div>

          <button
            id="closeSourcesBtn"
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-[#292929] shrink-0"
            title="Close"
            aria-label="Close drawer popup"
          >
            <X className="w-4 h-4 text-[#FFFFFF]" />
          </button>
        </div>

        {/* Filter & Actions Bar - Seamlessly merged without extra line */}
        <div className="pt-3.5 px-4 sm:px-6 pb-2 bg-[#0A0A0A] flex items-center gap-2.5 shrink-0">
          <div className="relative flex-1 min-w-0">
            <Search className="w-3.5 h-3.5 text-[#A3A3A3] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              placeholder="Filter sources by title..."
              className="w-full bg-[#111111] border border-[#292929] rounded-xl pl-8 pr-7 py-1.5 text-xs text-[#FFFFFF] placeholder-[#A3A3A3] focus:outline-none focus:border-[#FFFFFF]/40 transition-all shadow-2xs"
            />
            {sourceFilter && (
              <button
                type="button"
                onClick={() => setSourceFilter('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#A3A3A3] hover:text-[#FFFFFF] p-0.5 rounded cursor-pointer"
                title="Clear filter"
              >
                <X className="w-3 h-3" />
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
        <div className="px-4 sm:px-6 pb-4 overflow-y-auto max-h-[340px] space-y-2 bg-[#0A0A0A]">
          {sourceDocs.length > 0 && (
            <div className="flex items-center justify-between px-1 py-0.5 text-xs text-[#A3A3A3]">
              <span className="text-[11px] font-mono">
                {sourceFilter
                  ? `Showing ${filteredDocs.length} of ${sourceDocs.length}`
                  : `${activeSourcesCount} of ${sourceDocs.length} active`}
              </span>

              {onToggleAllSources && sourceDocs.length > 0 && (
                <button
                  type="button"
                  onClick={() => onToggleAllSources(!allSelected)}
                  className="text-[11px] font-medium text-[#A3A3A3] hover:text-[#FFFFFF] underline underline-offset-2 cursor-pointer shrink-0"
                >
                  {allSelected ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>
          )}

          {!isOnline && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[#111111] border border-[#292929] text-[#A3A3A3] text-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF] shrink-0" />
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
            <div className="text-center py-7 px-4">
              <div className="w-10 h-10 mx-auto mb-2.5 rounded-xl bg-[#171717] border border-[#292929] flex items-center justify-center text-[#A3A3A3]">
                <Database className="w-5 h-5 text-[#A3A3A3]" />
              </div>
              <p className="text-xs sm:text-sm font-semibold text-[#FFFFFF]">
                {!isOnline
                  ? 'Gateway Disconnected'
                  : sourceFilter
                    ? 'No matching sources found'
                    : 'No sources attached yet'}
              </p>
              <p className="text-[11px] text-[#A3A3A3] mt-1 max-w-sm mx-auto">
                {!isOnline
                  ? 'Connect to your pipeline gateway in Control Center to view indexed documents.'
                  : sourceFilter
                    ? `No sources match "${sourceFilter}". Try a different keyword.`
                    : 'Click Add Sources above to attach documents to this conversation.'}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="h-14 px-5 sm:px-6 border-t border-[#292929] bg-[#0A0A0A] flex items-center justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-[#FFFFFF] text-[#000000] hover:bg-[#FFFFFF]/90 transition-all shadow-sm active:scale-95 cursor-pointer"
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
