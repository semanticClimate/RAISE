import { Eye, FileText, Loader2, X } from 'lucide-react';
import React from 'react';
import { useDocumentViewerStore } from '../../../stores/useDocumentViewerStore';
import type { SourceDocument } from '../../../types';
import { formatBytes } from '../../../utils/formatters';

export interface SourceDocItemProps {
  doc: SourceDocument;
  isReady: boolean;
  onToggle?: (id: string) => void;
  onDelete: (id: string, name: string) => void;
  onViewPdf?: (filename: string, pageNumber?: number) => void;
  onOpenArtifactModal?: (documentName: string, type: 'markdown' | 'okf', url?: string) => void;
}

export const SourceDocItem: React.FC<SourceDocItemProps> = ({
  doc,
  isReady,
  onDelete,
  onViewPdf,
}) => {
  const isProcessing =
    doc.status === 'processing' ||
    (doc.uploadProgress !== undefined && doc.uploadProgress < 100);
  const progress = doc.uploadProgress ?? 0;

  return (
    <div
      onClick={() => {
        if (!isProcessing && isReady && doc.name.toLowerCase().endsWith('.pdf')) {
          useDocumentViewerStore.getState().openDocument(doc.name, 1);
          onViewPdf?.(doc.name, 1);
        }
      }}
      className={`p-3 rounded-xl border border-[#292929] bg-[#111111] hover:bg-[#171717] transition-all flex items-center justify-between gap-3 select-none ${
        isProcessing
          ? 'cursor-wait'
          : isReady && doc.name.toLowerCase().endsWith('.pdf')
            ? 'cursor-pointer'
            : ''
      }`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {/* File icon / processing spinner */}
        <div className="relative shrink-0">
          <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
            {isProcessing ? (
              <Loader2 className="w-4 h-4 text-[#FFFFFF] animate-spin" />
            ) : (
              <FileText className="w-4 h-4 text-[#FFFFFF]" />
            )}
          </div>
        </div>

        <div className="space-y-0.5 flex-1 min-w-0">
          <p className="text-xs font-semibold text-[#FFFFFF] truncate">
            {doc.name}
          </p>
          <div className="text-[11px] text-[#A3A3A3] flex items-center gap-1.5 truncate">
            <span className="font-mono">
              {doc.size === '0.0 MB' || doc.size === '0.0MB' || doc.size === '0 MB'
                ? doc.bytes
                  ? formatBytes(doc.bytes)
                  : '< 1 MB'
                : doc.size}
            </span>
            <span>•</span>
            {isProcessing ? (
              <span className="text-[#FFFFFF] font-mono text-[10px]">
                Processing {Math.round(progress)}%
              </span>
            ) : (
              <span>{doc.pages || 1} pp.</span>
            )}
          </div>
        </div>
      </div>

      {/* Right side: Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {isReady && doc.name.toLowerCase().endsWith('.pdf') && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              useDocumentViewerStore.getState().openDocument(doc.name, 1);
              onViewPdf?.(doc.name, 1);
            }}
            className="px-2.5 py-1 text-xs font-medium text-[#A3A3A3] hover:text-[#FFFFFF] bg-[#171717] hover:bg-[#292929] rounded-lg border border-[#292929] transition-all cursor-pointer flex items-center gap-1 shrink-0"
            title={`Preview ${doc.name}`}
            aria-label={`Preview ${doc.name}`}
          >
            <Eye className="w-3.5 h-3.5 text-[#A3A3A3]" />
            <span className="hidden sm:inline">Preview</span>
          </button>
        )}

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(doc.id, doc.name);
          }}
          className="p-1.5 text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] rounded-lg transition-all cursor-pointer"
          title={`Remove "${doc.name}" from drawer`}
          aria-label={`Remove ${doc.name} from drawer`}
        >
          <X className="w-3.5 h-3.5 text-[#A3A3A3]" />
        </button>
      </div>
    </div>
  );
};
