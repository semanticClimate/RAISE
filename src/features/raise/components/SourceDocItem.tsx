import React from 'react';
import { CircularUploadProgress } from '../../../components/ui/CircularUploadProgress';
import { useDocumentViewerStore } from '../../../stores/useDocumentViewerStore';
import type { SourceDocument } from '../../../types';
import { getDocumentStageLabel } from '../../../utils/documentStageUtils';
import { formatBytes } from '../../../utils/formatters';

export interface SourceDocItemProps {
  doc: SourceDocument;
  isReady: boolean;
  onToggle: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onViewPdf?: (filename: string, pageNumber?: number) => void;
  onOpenArtifactModal?: (name: string, type: 'markdown' | 'okf', url?: string) => void;
}

export const SourceDocItem: React.FC<SourceDocItemProps> = ({
  doc,
  isReady,
  onToggle,
  onDelete,
  onViewPdf,
  onOpenArtifactModal: _onOpenArtifactModal,
}) => {
  const isProcessing = !isReady;
  const progress = doc.uploadProgress ?? (isProcessing ? 45 : 100);

  return (
    <div
      onClick={() => !isProcessing && onToggle(doc.id)}
      className={`p-2.5 sm:p-3 rounded-xl border transition-all flex items-center justify-between gap-2.5 sm:gap-3 select-none ${
        isProcessing
          ? 'bg-amber-50/60 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/30 shadow-2xs cursor-wait'
          : doc.selected
            ? 'bg-indigo-50/70 border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/30 shadow-2xs cursor-pointer'
            : 'bg-slate-50/50 hover:bg-slate-100 border-slate-200/60 dark:bg-white/[0.02] dark:hover:bg-white/[0.05] dark:border-white/[0.06] opacity-75 hover:opacity-100 cursor-pointer'
      }`}
    >
      <div className="flex items-center gap-2.5 sm:gap-3 flex-1 min-w-0">
        {isProcessing ? (
          <div className="shrink-0 w-4 h-4 flex items-center justify-center">
            <div className="w-3.5 h-3.5 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
          </div>
        ) : (
          <input
            type="checkbox"
            checked={doc.selected}
            onChange={(e) => {
              e.stopPropagation();
              onToggle(doc.id);
            }}
            className="rounded border-slate-300 dark:border-white/20 bg-white dark:bg-white/10 text-indigo-600 focus:ring-0 cursor-pointer shrink-0"
          />
        )}

        {/* File icon */}
        <div className="relative shrink-0">
          <div
            className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center shrink-0 ${
              doc.color === 'rose'
                ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400'
                : doc.color === 'emerald'
                  ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400'
                  : doc.color === 'amber'
                    ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400'
                    : 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400'
            }`}
          >
            <svg
              className="w-3.5 h-3.5 sm:w-4 sm:h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.75"
                d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
          </div>
        </div>

        <div className="space-y-0.5 flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
            {doc.name}
          </p>
          <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 truncate">
            <span>
              {doc.size === '0.0 MB' || doc.size === '0.0MB' || doc.size === '0 MB'
                ? doc.bytes
                  ? formatBytes(doc.bytes)
                  : '< 1 MB'
                : doc.size}
            </span>
            <span>•</span>
            {isProcessing ? (
              <span className="text-amber-600 dark:text-amber-400 font-medium animate-pulse truncate">
                {getDocumentStageLabel(progress)} ({Math.round(progress)}%)
              </span>
            ) : (
              <>
                <span>{doc.pages} pp.</span>
                {doc.selected && (
                  <span className="ml-1 text-indigo-600 dark:text-[#a8c7fa] font-semibold">
                    Active Context
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Right: Progress indicator or action buttons */}
      <div className="flex items-center shrink-0">
        {isProcessing ? (
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-indigo-600 dark:text-[#a8c7fa]">
            <CircularUploadProgress
              progress={progress}
              size={22}
              strokeWidth={2}
              showPercentText={true}
            />
          </div>
        ) : (
          <div className="flex items-center gap-1">
            {isReady && doc.name.toLowerCase().endsWith('.pdf') && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  useDocumentViewerStore.getState().openDocument(doc.name, 1);
                  onViewPdf?.(doc.name, 1);
                }}
                className="px-2 py-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-500/15 dark:hover:bg-indigo-500/25 rounded-lg border border-indigo-200/80 dark:border-indigo-500/30 transition-all cursor-pointer flex items-center gap-1 shrink-0"
                title={`Open ${doc.name} in new tab`}
                aria-label={`Open ${doc.name} in new tab`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                  />
                </svg>
                <span className="hidden sm:inline">View PDF</span>
              </button>
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(doc.id, doc.name);
              }}
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:text-rose-400 dark:hover:bg-rose-500/10 rounded-lg transition-all cursor-pointer opacity-75 hover:opacity-100"
              title="Delete source"
              aria-label={`Delete source ${doc.name}`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
