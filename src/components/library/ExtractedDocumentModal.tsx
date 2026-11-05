import { AlertCircle, Check, Copy, Download, FileText, Loader2, Sparkles, X } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useEscapeKey, useScrollLock } from '../../hooks';
import { sourceService } from '../../services/SourceService';
import { AnswerMarkdown } from '../chat/AnswerMarkdown';

export interface ExtractedDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentName: string;
  type: 'markdown' | 'okf';
  url?: string;
}

export const ExtractedDocumentModal: React.FC<ExtractedDocumentModalProps> = ({
  isOpen,
  onClose,
  documentName,
  type,
  url,
}) => {
  const [content, setContent] = useState<string>('');
  const [jsonData, setJsonData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'rendered' | 'raw'>('rendered');

  useEscapeKey(onClose, isOpen);
  useScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen || !documentName) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);
    setContent('');
    setJsonData(null);

    const loadContent = async () => {
      try {
        if (type === 'markdown') {
          const targetUrl = url || sourceService.getExtractedMarkdownUrl(documentName);
          const mdText = await sourceService.fetchExtractedMarkdown(targetUrl);
          if (isMounted) {
            setContent(mdText);
          }
        } else {
          const targetUrl = url || sourceService.getOkfCatalogUrl(documentName);
          const okfRes = await sourceService.fetchOkfCatalog(targetUrl);
          if (isMounted) {
            setContent(okfRes.text);
            if (okfRes.data) {
              setJsonData(okfRes.data);
            }
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to load document artifact from backend');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadContent();

    return () => {
      isMounted = false;
    };
  }, [isOpen, documentName, type, url]);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!content) return;
    const blob = new Blob([content], {
      type: type === 'markdown' ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8',
    });
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download =
      type === 'markdown'
        ? `${documentName.replace(/\.[^/.]+$/, '')}.praised.md`
        : `${documentName.replace(/\.[^/.]+$/, '')}.okf_catalog.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
  };

  const modalTitle = type === 'markdown' ? 'prAISED Extracted Markdown' : 'OKF Catalog Overview';
  const modalSubtitle =
    type === 'markdown'
      ? 'Structure-preserving IBM Docling Markdown with layout & table extraction'
      : 'Open Knowledge Formulation (OKF) schema, entity models & knowledge graph catalog';

  return (
    <div
      className="fixed inset-0 z-[160] flex items-center justify-center p-[clamp(0.5rem,2vw,1.5rem)] bg-black/70 backdrop-blur-sm animate-in fade-in duration-150 select-none"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="w-[min(96vw,56rem)] h-[min(90vh,52rem)] bg-white dark:bg-[#141722] text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={modalTitle}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-200 dark:border-white/10 flex items-center justify-between bg-slate-50/80 dark:bg-white/[0.02]">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className={`p-2.5 rounded-xl border shrink-0 ${
                type === 'markdown'
                  ? 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400 border-indigo-200/60 dark:border-indigo-500/30'
                  : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400 border-emerald-200/60 dark:border-emerald-500/30'
              }`}
            >
              {type === 'markdown' ? (
                <FileText className="w-5 h-5" />
              ) : (
                <Sparkles className="w-5 h-5" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                  {modalTitle}
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-slate-200/70 dark:bg-white/10 text-slate-700 dark:text-slate-300 font-medium shrink-0">
                  {documentName}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-[#a8a8a8] truncate mt-0.5">
                {modalSubtitle}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {type === 'markdown' && (
              <div className="hidden sm:flex items-center p-0.5 bg-slate-100 dark:bg-white/5 rounded-lg border border-slate-200 dark:border-white/10 text-[11px] font-medium mr-1">
                <button
                  type="button"
                  onClick={() => setViewMode('rendered')}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                    viewMode === 'rendered'
                      ? 'bg-white dark:bg-[#1f2230] text-slate-900 dark:text-white shadow-2xs'
                      : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                  }`}
                >
                  Rendered
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('raw')}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                    viewMode === 'raw'
                      ? 'bg-white dark:bg-[#1f2230] text-slate-900 dark:text-white shadow-2xs'
                      : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                  }`}
                >
                  Raw Markdown
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={handleCopy}
              disabled={isLoading || Boolean(error)}
              className="p-1.5 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 border border-slate-200/80 dark:border-white/10 transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5 text-xs font-medium"
              title="Copy content to clipboard"
            >
              {isCopied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-500" />
                  <span className="text-[11px] text-emerald-500 hidden md:inline">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span className="text-[11px] hidden md:inline">Copy</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleDownload}
              disabled={isLoading || Boolean(error)}
              className="p-1.5 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 border border-slate-200/80 dark:border-white/10 transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5 text-xs font-medium"
              title="Download file"
            >
              <Download className="w-4 h-4" />
              <span className="text-[11px] hidden md:inline">Download</span>
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="p-1.5 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer ml-1"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 select-text bg-white dark:bg-[#0f111a]">
          {isLoading ? (
            <div className="h-full flex flex-col items-center justify-center text-xs text-slate-400 dark:text-slate-500 gap-3">
              <Loader2 className="w-7 h-7 text-indigo-500 animate-spin" />
              <span className="font-medium">
                Fetching {type === 'markdown' ? 'prAISED extracted markdown' : 'OKF catalog'} from gateway...
              </span>
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 flex items-center justify-center text-amber-500 mb-3">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
                Content Unavailable
              </h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">{error}</p>
              <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                Ensure IBM Docling parser has completed processing for {documentName}
              </span>
            </div>
          ) : content.trim().length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 text-xs">
              <FileText className="w-8 h-8 mb-2 opacity-50" />
              <span>Document returned empty content</span>
            </div>
          ) : type === 'markdown' && viewMode === 'rendered' ? (
            <div className="prose prose-slate dark:prose-invert max-w-none text-xs sm:text-sm">
              <AnswerMarkdown content={content} />
            </div>
          ) : (
            <pre className="p-4 rounded-xl bg-slate-50 dark:bg-[#161824] border border-slate-200 dark:border-white/10 text-slate-800 dark:text-slate-200 font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {jsonData ? JSON.stringify(jsonData, null, 2) : content}
            </pre>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-200 dark:border-white/10 bg-slate-50/80 dark:bg-white/[0.02] flex items-center justify-between text-xs text-slate-500 dark:text-[#a8a8a8]">
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span>{content.length.toLocaleString()} characters</span>
            <span>•</span>
            <span>{content.split(/\s+/).filter(Boolean).length.toLocaleString()} words</span>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100 text-xs font-medium transition-all active:scale-95 cursor-pointer shadow-xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
