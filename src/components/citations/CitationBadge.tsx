import { ExternalLink, FileText, Layers } from 'lucide-react';
import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { sourceService } from '../../services/SourceService';
import type { Citation } from '../../types';
import { extractVerifiedPageNumber } from '../../utils/citationParser';

import { getApiBaseUrl } from '../../app/config';

export interface CitationBadgeProps {
  index?: number;
  indices?: number[];
  citation?: Citation;
  citations?: Citation[];
  onViewPdf?: (fileName: string, page: number) => void;
}

interface CitationItemDetail {
  index: number;
  pageNumber?: number;
  fileName: string;
  pdfUrl?: string;
  singlePagePdfUrl?: string;
  singlePageImageUrl?: string;
  singlePageViewUrl?: string;
  heading?: string;
  plainText?: string;
}

function resolveCitationDetail(cit?: Citation, fallbackIndex: number = 1): CitationItemDetail {
  const pageNumber = extractVerifiedPageNumber(cit);

  const rawFileName =
    cit?.pdf_filename ||
    (cit as any)?.filename ||
    (cit as any)?.file_name ||
    (cit as any)?.document_name ||
    (cit as any)?.doc_name ||
    (cit as any)?.source ||
    (cit as any)?.metadata?.pdf_filename ||
    (cit as any)?.metadata?.filename;

  const fileName =
    rawFileName && rawFileName !== 'Document' ? rawFileName : rawFileName || 'Audited Document';

  const base = getApiBaseUrl().replace(/\/+$/, '');

  const singlePagePdfUrl = cit?.page_url
    ? `${base}${cit.page_url.startsWith('/') ? '' : '/'}${cit.page_url}`
    : rawFileName && pageNumber && pageNumber > 0
      ? sourceService.getSinglePagePdfUrl(rawFileName, pageNumber)
      : undefined;

  const singlePageImageUrl = cit?.page_image_url
    ? `${base}${cit.page_image_url.startsWith('/') ? '' : '/'}${cit.page_image_url}`
    : rawFileName && pageNumber && pageNumber > 0
      ? sourceService.getSinglePageImageUrl(rawFileName, pageNumber)
      : undefined;

  const singlePageViewUrl = cit?.page_view_url
    ? `${base}${cit.page_view_url.startsWith('/') ? '' : '/'}${cit.page_view_url}`
    : rawFileName && pageNumber && pageNumber > 0
      ? sourceService.getSinglePageViewUrl(rawFileName, pageNumber)
      : undefined;

  const pdfUrl = rawFileName ? sourceService.getPdfUrl(rawFileName, pageNumber) : undefined;

  return {
    index: cit?.citation_index ?? fallbackIndex,
    pageNumber,
    fileName,
    pdfUrl,
    singlePagePdfUrl,
    singlePageImageUrl,
    singlePageViewUrl,
    heading: cit?.heading,
    plainText: cit?.plain_text,
  };
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  index,
  indices,
  citation,
  citations,
  onViewPdf,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const leaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleMouseEnter = () => {
    if (leaveTimeoutRef.current) {
      clearTimeout(leaveTimeoutRef.current);
      leaveTimeoutRef.current = null;
    }
    setShowTooltip(true);
  };

  const handleMouseLeave = () => {
    leaveTimeoutRef.current = setTimeout(() => {
      setShowTooltip(false);
    }, 180);
  };

  useEffect(() => {
    return () => {
      if (leaveTimeoutRef.current) {
        clearTimeout(leaveTimeoutRef.current);
      }
    };
  }, []);

  // Determine list of citations to show
  const rawList: { cit?: Citation; idx: number }[] = [];
  if (citations && citations.length > 0) {
    citations.forEach((c, i) => {
      const idx = indices?.[i] ?? c.citation_index ?? (index ? index + i : i + 1);
      rawList.push({ cit: c, idx });
    });
  } else if (indices && indices.length > 0) {
    indices.forEach((idx) => {
      rawList.push({ cit: citation, idx });
    });
  } else {
    rawList.push({ cit: citation, idx: index ?? 1 });
  }

  const items: CitationItemDetail[] = rawList.map((item) =>
    resolveCitationDetail(item.cit, item.idx)
  );

  const isMultiple = items.length > 1;
  const firstItem = items[0] || {
    index: index ?? 1,
    fileName: 'Audited Document',
    pageNumber: undefined,
  };
  const buttonLabel = isMultiple
    ? `[${items.map((it) => it.index).join(', ')}]`
    : `[${firstItem.index}]`;

  const handleBadgeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isMultiple) {
      setShowTooltip((prev) => !prev);
    } else if (onViewPdf && firstItem.fileName && firstItem.fileName !== 'Audited Document') {
      onViewPdf(firstItem.fileName, firstItem.pageNumber || 1);
    } else {
      setShowTooltip((prev) => !prev);
    }
  };

  const handleOpenDoc = (
    e: React.MouseEvent,
    pdfUrl?: string,
    fileName?: string,
    page?: number
  ) => {
    e.stopPropagation();
    if (onViewPdf && fileName) {
      onViewPdf(fileName, page || 1);
      return;
    }
    if (pdfUrl && typeof window !== 'undefined') {
      window.open(pdfUrl, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <span className="relative inline-block mx-0.5 align-baseline">
      <button
        type="button"
        onClick={handleBadgeClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleMouseEnter}
        onBlur={handleMouseLeave}
        aria-label={
          isMultiple
            ? `Citations ${buttonLabel}`
            : `Citation [${firstItem.index}]: ${firstItem.fileName}${firstItem.pageNumber ? `, page ${firstItem.pageNumber}` : ''}`
        }
        className="inline-flex items-center justify-center px-1.5 py-0.5 text-[11px] font-mono font-medium rounded bg-slate-100/90 hover:bg-slate-200/90 dark:bg-white/[0.07] dark:hover:bg-white/[0.12] text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white border border-slate-300/80 hover:border-slate-400 dark:border-white/10 dark:hover:border-white/20 transition-all duration-150 cursor-pointer shadow-2xs hover:scale-105 active:scale-95 select-none"
        title={
          isMultiple
            ? `Multiple citations ${buttonLabel} - Click to inspect`
            : firstItem.fileName
              ? `Click to view ${firstItem.fileName}${firstItem.pageNumber ? ` at Page ${firstItem.pageNumber}` : ''}`
              : `Citation [${firstItem.index}]`
        }
      >
        <span>{buttonLabel}</span>
        {!isMultiple && firstItem.pageNumber !== undefined && firstItem.pageNumber > 0 && (
          <span className="ml-1 px-1 py-0.2 rounded text-[9.5px] font-mono font-semibold bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-400/25">
            p.{firstItem.pageNumber}
          </span>
        )}
      </button>

      {showTooltip && (
        <div
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className={`absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 ${
            isMultiple ? 'w-64 sm:w-72 max-h-80' : 'w-56 sm:w-64 max-h-72'
          } max-w-[calc(100vw-2rem)] p-2.5 bg-black/95 dark:bg-black/95 text-white backdrop-blur-md border border-white/15 rounded-xl shadow-2xl shadow-black/80 text-left pointer-events-auto animate-in fade-in zoom-in-95 duration-150 select-text overflow-y-auto`}
          role="tooltip"
        >
          {isMultiple && (
            <div className="flex items-center gap-1.5 pb-1.5 mb-2 border-b border-white/10 text-[11px] font-semibold text-slate-300">
              <Layers className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>Citations ({items.length})</span>
            </div>
          )}

          <div className="space-y-2.5 divide-y divide-white/10">
            {items.map((item, i) => (
              <div key={`${item.index}-${i}`} className={i > 0 ? 'pt-2' : ''}>
                {/* Header with Document Name & Single Page Badge */}
                <div className="flex items-center justify-between gap-1.5">
                  <div
                    onClick={(e) =>
                      handleOpenDoc(e, item.pdfUrl, item.fileName, item.pageNumber || 1)
                    }
                    className="flex items-center gap-1 text-[11.5px] font-semibold text-slate-100 hover:text-white transition-colors cursor-pointer min-w-0"
                    title="Click to open PDF document"
                  >
                    <FileText className="w-3 h-3 shrink-0 text-slate-400" />
                    <span className="truncate">{item.fileName}</span>
                  </div>
                  {item.pageNumber !== undefined && item.pageNumber > 0 ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onViewPdf && item.fileName) {
                          onViewPdf(item.fileName, item.pageNumber || 1);
                          return;
                        }
                        const targetUrl = item.singlePagePdfUrl || item.pdfUrl;
                        if (targetUrl && typeof window !== 'undefined') {
                          window.open(targetUrl, '_blank', 'noopener,noreferrer');
                        }
                      }}
                      title={`Open Page ${item.pageNumber} in viewer`}
                      className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold bg-blue-500/15 hover:bg-blue-500/25 text-blue-300 hover:text-white border border-blue-500/30 px-2 py-0.5 rounded cursor-pointer transition-all shrink-0 hover:scale-105 active:scale-95 shadow-2xs"
                    >
                      <span>Page {item.pageNumber}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  ) : (
                    <span className="text-[10px] font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700/60 px-1.5 py-0.2 rounded shrink-0">
                      Doc Source
                    </span>
                  )}
                </div>

                {/* Heading */}
                {item.heading && (
                  <div className="text-[11px] font-medium text-slate-300 mt-1 line-clamp-1 flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-slate-400 shrink-0" />
                    <span className="truncate">{item.heading}</span>
                  </div>
                )}

                {/* Excerpt Quote */}
                {item.plainText && (
                  <blockquote className="text-[10.5px] leading-relaxed text-slate-300 line-clamp-2 mt-1.5 italic bg-white/[0.04] p-1.5 rounded border-l-2 border-slate-500">
                    "{item.plainText}"
                  </blockquote>
                )}

                {/* Footer with Single Page & View PDF Links */}
                <div className="flex items-center justify-between text-[10.5px] pt-1.5 mt-1 border-t border-white/5">
                  {item.singlePagePdfUrl ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (typeof window !== 'undefined') {
                          window.open(item.singlePagePdfUrl, '_blank', 'noopener,noreferrer');
                        }
                      }}
                      className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 hover:underline cursor-pointer transition-colors text-[10.5px] font-medium"
                      title="Open isolated 1-page PDF (~72 KB in 25ms)"
                    >
                      <span>⚡ Page {item.pageNumber || 1} Only</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  ) : (
                    <span className="text-[10px] text-slate-500 font-mono">Source</span>
                  )}

                  {item.pdfUrl && (
                    <button
                      type="button"
                      onClick={(e) =>
                        handleOpenDoc(e, item.pdfUrl, item.fileName, item.pageNumber || 1)
                      }
                      className="inline-flex items-center gap-1 text-slate-400 hover:text-white hover:underline cursor-pointer transition-colors text-[10.5px] font-medium"
                      title="Open full document"
                    >
                      <span>Full Doc</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Arrow / Caret - Black to match tooltip */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-black dark:border-t-black drop-shadow-2xs pointer-events-none" />
        </div>
      )}
    </span>
  );
};
