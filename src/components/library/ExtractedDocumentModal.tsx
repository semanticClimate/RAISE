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
        ? `${documentName.replace(/\.[^/.]+$/, '')}.parsed.md`
        : `${documentName.replace(/\.[^/.]+$/, '')}.okf_catalog.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
  };

  const modalTitle = type === 'markdown' ? 'Parsed Extracted Markdown' : 'OKF Catalog Overview';
  const modalSubtitle =
    type === 'markdown'
      ? 'Structure-preserving IBM Docling Markdown with layout & table extraction'
      : 'Open Knowledge Formulation (OKF) schema, entity models & knowledge graph catalog';

  return (
    <div
      className="fixed inset-0 z-[160] flex items-center justify-center p-3 sm:p-5 bg-[#000000]/80 backdrop-blur-sm animate-in fade-in duration-150 select-none font-sans"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="w-[min(96vw,56rem)] h-[min(90vh,52rem)] bg-[#0A0A0A] text-[#FFFFFF] border border-[#292929] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={modalTitle}
      >
        {/* Header */}
        <div className="h-16 px-5 sm:px-6 border-b border-[#292929] bg-[#0A0A0A] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
              {type === 'markdown' ? (
                <FileText className="w-4 h-4 text-[#FFFFFF]" />
              ) : (
                <Sparkles className="w-4 h-4 text-[#FFFFFF]" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-semibold text-[#FFFFFF] truncate">
                  {modalTitle}
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[#171717] border border-[#292929] text-[#A3A3A3] font-medium shrink-0">
                  {documentName}
                </span>
              </div>
              <p className="text-xs text-[#A3A3A3] truncate mt-0.5">
                {modalSubtitle}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 shrink-0">
            {type === 'markdown' && (
              <div className="hidden sm:flex items-center p-0.5 bg-[#111111] rounded-lg border border-[#292929] text-xs font-medium mr-1">
                <button
                  type="button"
                  onClick={() => setViewMode('rendered')}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                    viewMode === 'rendered'
                      ? 'bg-[#FFFFFF] text-[#000000] font-semibold shadow-xs'
                      : 'text-[#A3A3A3] hover:text-[#FFFFFF]'
                  }`}
                >
                  Rendered
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('raw')}
                  className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                    viewMode === 'raw'
                      ? 'bg-[#FFFFFF] text-[#000000] font-semibold shadow-xs'
                      : 'text-[#A3A3A3] hover:text-[#FFFFFF]'
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
              className="p-1.5 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] border border-[#292929] transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5 text-xs font-medium"
              title="Copy content to clipboard"
            >
              {isCopied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-[#FFFFFF]" />
                  <span className="text-[11px] text-[#FFFFFF] hidden md:inline">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-[#A3A3A3]" />
                  <span className="text-[11px] text-[#A3A3A3] hidden md:inline">Copy</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleDownload}
              disabled={isLoading || Boolean(error)}
              className="p-1.5 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] border border-[#292929] transition-colors disabled:opacity-40 cursor-pointer flex items-center gap-1.5 text-xs font-medium"
              title="Download file to PC"
            >
              <Download className="w-3.5 h-3.5 text-[#A3A3A3]" />
              <span className="text-[11px] text-[#A3A3A3] hidden md:inline">Export</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-[#292929] shrink-0"
              aria-label="Close"
            >
              <X className="w-4 h-4 text-[#FFFFFF]" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-7 min-h-0 bg-[#0A0A0A] font-sans">
          {isLoading ? (
            <div className="h-full flex flex-col items-center justify-center text-xs text-[#A3A3A3] gap-3">
              <Loader2 className="w-6 h-6 text-[#FFFFFF] animate-spin" />
              <span>Fetching parsed artifact from GraphRAG vault...</span>
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-xs text-[#A3A3A3] gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#171717] border border-[#292929] flex items-center justify-center text-[#A3A3A3]">
                <AlertCircle className="w-5 h-5 text-[#FFFFFF]" />
              </div>
              <p className="font-semibold text-sm text-[#FFFFFF]">Document Artifact Not Available</p>
              <p className="max-w-md text-[#A3A3A3] leading-relaxed">{error}</p>
            </div>
          ) : type === 'markdown' && viewMode === 'raw' ? (
            <pre className="p-4 rounded-xl bg-[#111111] border border-[#292929] text-xs font-mono text-[#FFFFFF] whitespace-pre-wrap break-all leading-relaxed overflow-x-auto select-text">
              {content}
            </pre>
          ) : type === 'markdown' ? (
            <div className="max-w-4xl mx-auto prose dark:prose-invert prose-sm select-text text-[#FFFFFF]">
              <AnswerMarkdown content={content} />
            </div>
          ) : jsonData ? (
            <div className="space-y-4 max-w-4xl mx-auto select-text">
              {jsonData.catalog_summary && (
                <div className="p-4 rounded-xl bg-[#111111] border border-[#292929]">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-[#A3A3A3] mb-1">
                    Catalog Summary
                  </h4>
                  <p className="text-sm text-[#FFFFFF] leading-relaxed">
                    {jsonData.catalog_summary}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-[#111111] border border-[#292929]">
                  <span className="text-[11px] text-[#A3A3A3] block">Chunks</span>
                  <span className="text-base font-semibold text-[#FFFFFF] font-mono mt-0.5 block">
                    {jsonData.total_chunks || 0}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-[#111111] border border-[#292929]">
                  <span className="text-[11px] text-[#A3A3A3] block">Key Concepts</span>
                  <span className="text-base font-semibold text-[#FFFFFF] font-mono mt-0.5 block">
                    {jsonData.entity_count || jsonData.entities?.length || 0}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-[#111111] border border-[#292929]">
                  <span className="text-[11px] text-[#A3A3A3] block">Relationships</span>
                  <span className="text-base font-semibold text-[#FFFFFF] font-mono mt-0.5 block">
                    {jsonData.relationships_count || jsonData.triples?.length || 0}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-[#111111] border border-[#292929]">
                  <span className="text-[11px] text-[#A3A3A3] block">Data Grounding</span>
                  <span className="text-base font-semibold text-[#FFFFFF] font-mono mt-0.5 block">
                    100% OKF
                  </span>
                </div>
              </div>

              {content && (
                <div className="p-4 rounded-xl bg-[#111111] border border-[#292929]">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-[#A3A3A3] mb-2">
                    Raw OKF Markdown
                  </h4>
                  <pre className="text-xs font-mono text-[#FFFFFF] whitespace-pre-wrap break-all leading-relaxed overflow-x-auto">
                    {content}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <pre className="p-4 rounded-xl bg-[#111111] border border-[#292929] text-xs font-mono text-[#FFFFFF] whitespace-pre-wrap break-all leading-relaxed overflow-x-auto select-text">
              {content}
            </pre>
          )}
        </div>

        {/* Footer */}
        <div className="h-14 px-5 sm:px-6 border-t border-[#292929] bg-[#0A0A0A] flex items-center justify-between shrink-0">
          <span className="text-xs font-mono text-[#A3A3A3]">
            {type === 'markdown'
              ? `${(content.length / 1024).toFixed(1)} KB extracted text`
              : 'OKF Catalog Profile'}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] text-xs font-semibold transition-all active:scale-95 cursor-pointer shadow-sm"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
