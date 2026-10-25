import { ExternalLink, FileText, Globe } from 'lucide-react';
import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { getApiBaseUrl } from '../../app/config';
import { sourceService } from '../../services/SourceService';
import type { Citation } from '../../types';
import { extractVerifiedPageNumber } from '../../utils/citationParser';

export interface CitationBadgeProps {
  index?: number;
  indices?: number[];
  citation?: Citation;
  citations?: Citation[];
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
}

export interface CitationItemDetail {
  index: number;
  pageNumber?: number;
  fileName: string;
  pdfUrl?: string;
  singlePagePdfUrl?: string;
  singlePageImageUrl?: string;
  singlePageViewUrl?: string;
  primaryUrl: string;
  heading?: string;
  plainText?: string;
  isWeb?: boolean;
  webUrl?: string;
}

export function isSafeHttpUrl(urlString?: string): boolean {
  if (!urlString || typeof urlString !== 'string') return false;
  const trimmed = urlString.trim();
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) return false;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function isSafeUrl(urlString?: string): boolean {
  if (!urlString || typeof urlString !== 'string') return false;
  const trimmed = urlString.trim();
  if (trimmed === '#' || trimmed.startsWith('#')) return false;
  try {
    const parsed = new URL(
      trimmed,
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://localhost'
    );
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'blob:';
  } catch {
    return false;
  }
}

export function resolveCitationDetail(
  cit?: Citation,
  fallbackIndex: number = 1
): CitationItemDetail {
  const pageNumber = extractVerifiedPageNumber(cit);

  const citRecord = cit && typeof cit === 'object' ? (cit as Record<string, unknown>) : null;
  const citMeta =
    citRecord?.metadata && typeof citRecord.metadata === 'object'
      ? (citRecord.metadata as Record<string, unknown>)
      : null;

  let rawFileName: string | undefined =
    typeof cit?.pdf_filename === 'string'
      ? cit.pdf_filename
      : typeof citRecord?.filename === 'string'
        ? citRecord.filename
        : typeof citRecord?.file_name === 'string'
          ? citRecord.file_name
          : typeof citRecord?.document_name === 'string'
            ? citRecord.document_name
            : typeof citRecord?.doc_name === 'string'
              ? citRecord.doc_name
              : typeof citRecord?.source === 'string'
                ? citRecord.source
                : typeof citMeta?.pdf_filename === 'string'
                  ? citMeta.pdf_filename
                  : typeof citMeta?.filename === 'string'
                    ? citMeta.filename
                    : undefined;

  const rawUrl =
    typeof cit?.url === 'string'
      ? cit.url.trim()
      : typeof citRecord?.url === 'string'
        ? (citRecord.url as string).trim()
        : undefined;

  const validRawUrl = isSafeHttpUrl(rawUrl) ? rawUrl : undefined;
  const validFileNameUrl = isSafeHttpUrl(rawFileName) ? rawFileName : undefined;

  const isWeb =
    cit?.source_type === 'EXTERNAL_PUBLIC_RECORD' ||
    cit?.source_type?.toLowerCase() === 'web' ||
    Boolean(validRawUrl) ||
    Boolean(validFileNameUrl);

  const webUrl = validRawUrl || validFileNameUrl;

  let fileName = rawFileName || 'Audited Document';

  if (isWeb) {
    if (cit?.heading && cit.heading.trim().length > 0) {
      fileName = cit.heading.trim();
    } else if (webUrl) {
      try {
        const u = new URL(webUrl);
        const lastPart = u.pathname.split('/').filter(Boolean).pop();
        if (lastPart) {
          try {
            fileName = decodeURIComponent(lastPart).replace(/_/g, ' ');
          } catch {
            fileName = lastPart.replace(/_/g, ' ');
          }
        } else {
          fileName = u.hostname;
        }
      } catch {
        fileName = 'Public Web Source';
      }
    } else {
      fileName = 'Public Web Record';
    }
  } else if (typeof rawFileName === 'string') {
    // Clean directory paths if present (e.g. /app/documents/BRIC.pdf -> BRIC.pdf)
    rawFileName = rawFileName.trim();
    const lastSlash = Math.max(rawFileName.lastIndexOf('/'), rawFileName.lastIndexOf('\\'));
    if (lastSlash >= 0) {
      rawFileName = rawFileName.slice(lastSlash + 1).trim();
    }
    // If still generic or missing, recover from chunk_id
    if (!rawFileName || rawFileName === 'Document' || rawFileName === 'Audited Document') {
      const chunkId =
        typeof cit?.chunk_id === 'string'
          ? cit.chunk_id
          : typeof citRecord?.id === 'string'
            ? citRecord.id
            : typeof citMeta?.chunk_id === 'string'
              ? citMeta.chunk_id
              : undefined;
      if (typeof chunkId === 'string') {
        const stemMatch = chunkId.match(/^([a-zA-Z0-9_\-\s]+?)(?:_p\d+|_parent|\.pdf|$)/i);
        if (
          stemMatch?.[1] &&
          stemMatch[1].length > 3 &&
          !stemMatch[1].startsWith('chk_') &&
          !stemMatch[1].startsWith('cit-')
        ) {
          rawFileName = stemMatch[1].endsWith('.pdf') ? stemMatch[1] : `${stemMatch[1]}.pdf`;
        }
      }
    }
    fileName = rawFileName || 'Audited Document';
  }

  const base = getApiBaseUrl().replace(/\/+$/, '');
  const safePage = pageNumber && pageNumber > 0 ? pageNumber : 1;

  const singlePagePdfUrl = isWeb
    ? undefined
    : cit?.page_url
      ? `${base}${cit.page_url.startsWith('/') ? '' : '/'}${cit.page_url}`
      : rawFileName
        ? sourceService.getSinglePagePdfUrl(rawFileName, safePage)
        : undefined;

  const singlePageImageUrl = isWeb
    ? undefined
    : cit?.page_image_url
      ? `${base}${cit.page_image_url.startsWith('/') ? '' : '/'}${cit.page_image_url}`
      : rawFileName
        ? sourceService.getSinglePageImageUrl(rawFileName, safePage)
        : undefined;

  const singlePageViewUrl = isWeb
    ? undefined
    : cit?.page_view_url
      ? `${base}${cit.page_view_url.startsWith('/') ? '' : '/'}${cit.page_view_url}`
      : rawFileName
        ? sourceService.getSinglePageViewUrl(rawFileName, safePage)
        : undefined;

  const pdfUrl = isWeb
    ? undefined
    : rawFileName
      ? sourceService.getPdfUrl(rawFileName, pageNumber)
      : undefined;

  // Primary URL prioritizes external web URL for web records, otherwise interactive single-page view or full PDF
  const candidatePrimaryUrl =
    (isWeb && webUrl
      ? webUrl
      : (pageNumber && pageNumber > 0 ? singlePageViewUrl || singlePagePdfUrl : undefined) ||
        pdfUrl);

  const primaryUrl = isSafeUrl(candidatePrimaryUrl) ? (candidatePrimaryUrl as string) : '#';

  return {
    index: cit?.citation_index ?? fallbackIndex,
    pageNumber: isWeb ? undefined : pageNumber,
    fileName,
    pdfUrl,
    singlePagePdfUrl,
    singlePageImageUrl,
    singlePageViewUrl,
    primaryUrl,
    heading: cit?.heading,
    plainText: cit?.plain_text,
    isWeb,
    webUrl,
  };
}

interface CitationSingleBadgeProps {
  item: CitationItemDetail;
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
}

const CitationSingleBadge: React.FC<CitationSingleBadgeProps> = ({ item, onViewPdf }) => {
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

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.stopPropagation();
    if (!item.isWeb && onViewPdf && item.fileName && item.fileName !== 'Audited Document') {
      e.preventDefault();
      onViewPdf(item.fileName, item.pageNumber || 1, 'page');
      return;
    }
    if (!item.primaryUrl || item.primaryUrl === '#' || !isSafeUrl(item.primaryUrl)) {
      e.preventDefault();
    }
  };

  const handleOpenPageOnly = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.stopPropagation();
    if (!item.isWeb && onViewPdf && item.fileName && item.fileName !== 'Audited Document') {
      e.preventDefault();
      onViewPdf(item.fileName, item.pageNumber || 1, 'page');
      return;
    }
    const target = item.isWeb
      ? item.webUrl || item.primaryUrl
      : item.singlePageViewUrl || item.singlePagePdfUrl || item.pdfUrl;
    if (!target || target === '#' || !isSafeUrl(target)) {
      e.preventDefault();
    }
  };

  const handleOpenFullPdfFromDiv = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (!item.isWeb && onViewPdf && item.fileName && item.fileName !== 'Audited Document') {
      onViewPdf(item.fileName, item.pageNumber || 1, 'full');
      return;
    }
    const target = item.isWeb ? item.webUrl || item.primaryUrl : item.pdfUrl;
    if (target && target !== '#' && isSafeUrl(target) && typeof window !== 'undefined') {
      window.open(target, '_blank', 'noopener,noreferrer');
    }
  };

  const handleOpenFullPdfFromLink = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.stopPropagation();
    if (!item.isWeb && onViewPdf && item.fileName && item.fileName !== 'Audited Document') {
      e.preventDefault();
      onViewPdf(item.fileName, item.pageNumber || 1, 'full');
      return;
    }
    const target = item.isWeb ? item.webUrl || item.primaryUrl : item.pdfUrl;
    if (!target || target === '#' || !isSafeUrl(target)) {
      e.preventDefault();
    }
  };

  return (
    <span className="relative inline-block mx-0.5 align-baseline">
      <a
        href={item.primaryUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleMouseEnter}
        onBlur={handleMouseLeave}
        aria-label={`Citation [${item.index}]: ${item.fileName}${!item.isWeb && item.pageNumber ? `, page ${item.pageNumber}` : ''}`}
        title={
          item.isWeb
            ? `Click to open external web article: ${item.fileName}`
            : `Click to open ${item.fileName}${item.pageNumber ? ` at Page ${item.pageNumber}` : ''} in a new tab`
        }
        className={`inline-flex items-center justify-center gap-0.5 px-1.5 py-0.5 text-[11px] font-mono font-semibold rounded-md border transition-all duration-150 cursor-pointer shadow-2xs hover:scale-105 active:scale-95 select-none no-underline group ${
          item.isWeb
            ? 'bg-cyan-50/95 hover:bg-cyan-100/95 text-cyan-700 hover:text-cyan-900 dark:bg-cyan-950/60 dark:hover:bg-cyan-900/80 dark:text-cyan-300 dark:hover:text-cyan-100 border-cyan-200/90 hover:border-cyan-400 dark:border-cyan-700/60 dark:hover:border-cyan-500'
            : 'bg-blue-50/95 hover:bg-blue-100/95 text-blue-700 hover:text-blue-900 dark:bg-blue-950/60 dark:hover:bg-blue-900/80 dark:text-blue-300 dark:hover:text-blue-100 border-blue-200/90 hover:border-blue-400 dark:border-blue-700/60 dark:hover:border-blue-500'
        }`}
      >
        <span>[{item.index}]</span>
        {!item.isWeb && item.pageNumber !== undefined && item.pageNumber > 0 && (
          <span className="ml-0.5 px-1 py-0.2 rounded text-[9px] font-mono font-semibold bg-blue-200/70 dark:bg-blue-900/70 text-blue-900 dark:text-blue-200">
            p.{item.pageNumber}
          </span>
        )}
        {item.isWeb ? (
          <Globe className="w-2.5 h-2.5 ml-0.5 opacity-60 group-hover:opacity-100 transition-opacity text-cyan-500" />
        ) : (
          <ExternalLink className="w-2.5 h-2.5 ml-0.5 opacity-60 group-hover:opacity-100 transition-opacity" />
        )}
      </a>

      {showTooltip && (
        <div
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 sm:w-72 max-h-80 max-w-[calc(100vw-2rem)] p-3 bg-slate-950 text-white backdrop-blur-md border border-slate-700/80 rounded-xl shadow-2xl text-left pointer-events-auto animate-in fade-in zoom-in-95 duration-150 select-text overflow-y-auto"
          role="tooltip"
        >
          {/* Header with Document Name & Page Badge */}
          <div className="flex items-center justify-between gap-1.5 pb-1.5 border-b border-white/10">
            <div
              onClick={handleOpenFullPdfFromDiv}
              className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-100 hover:text-cyan-300 transition-colors cursor-pointer min-w-0"
              title={
                item.isWeb
                  ? 'Click to open web page in new tab'
                  : 'Click to open full PDF document in new tab'
              }
            >
              {item.isWeb ? (
                <Globe className="w-3.5 h-3.5 shrink-0 text-cyan-400" />
              ) : (
                <FileText className="w-3.5 h-3.5 shrink-0 text-blue-400" />
              )}
              <span className="truncate">{item.fileName}</span>
            </div>
            {item.isWeb ? (
              <span className="inline-flex items-center text-[10px] font-mono font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-1.5 py-0.2 rounded shrink-0">
                Web Record
              </span>
            ) : item.pageNumber !== undefined && item.pageNumber > 0 ? (
              <span className="inline-flex items-center text-[10px] font-mono font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 px-1.5 py-0.2 rounded shrink-0">
                Page {item.pageNumber}
              </span>
            ) : (
              <span className="text-[10px] font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700/60 px-1.5 py-0.2 rounded shrink-0">
                Document
              </span>
            )}
          </div>

          {/* Heading */}
          {item.heading && (
            <div className="text-[11px] font-medium text-slate-300 mt-2 line-clamp-1 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
              <span className="truncate">{item.heading}</span>
            </div>
          )}

          {/* Excerpt Quote */}
          {item.plainText && (
            <blockquote className="text-[10.5px] leading-relaxed text-slate-300 line-clamp-3 mt-1.5 italic bg-white/[0.04] p-2 rounded-lg border-l-2 border-cyan-500">
              "{item.plainText}"
            </blockquote>
          )}

          {/* Explicit Quick Action Buttons */}
          <div className="grid grid-cols-2 gap-1.5 pt-2 mt-2 border-t border-white/10">
            {item.isWeb ? (
              <a
                href={item.webUrl || item.primaryUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleOpenPageOnly}
                className="col-span-2 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10.5px] font-medium font-sans bg-cyan-600 hover:bg-cyan-500 text-white rounded-md shadow-2xs hover:scale-[1.01] active:scale-95 transition-all text-center cursor-pointer no-underline"
                title="Open public web article in new tab"
              >
                <Globe className="w-3 h-3" />
                <span>Open Public Web Article</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            ) : (
              <>
                <a
                  href={item.singlePageViewUrl || item.singlePagePdfUrl || item.pdfUrl || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={handleOpenPageOnly}
                  className="inline-flex items-center justify-center gap-1 px-2 py-1 text-[10.5px] font-medium font-sans bg-blue-600 hover:bg-blue-500 text-white rounded-md shadow-2xs hover:scale-[1.02] active:scale-95 transition-all text-center cursor-pointer no-underline"
                  title="Open isolated single page view in new tab"
                >
                  <span>⚡ Page {item.pageNumber || 1}</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>

                <a
                  href={item.pdfUrl || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={handleOpenFullPdfFromLink}
                  className="inline-flex items-center justify-center gap-1 px-2 py-1 text-[10.5px] font-medium font-sans bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700 rounded-md shadow-2xs hover:scale-[1.02] active:scale-95 transition-all text-center cursor-pointer no-underline"
                  title="Open complete PDF document in new tab"
                >
                  <span>📖 Full PDF</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </>
            )}
          </div>

          {/* Caret */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-950 pointer-events-none" />
        </div>
      )}
    </span>
  );
};

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  index,
  indices,
  citation,
  citations,
  onViewPdf,
}) => {
  // Collect all citations to represent
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

  if (items.length === 0) {
    return null;
  }

  // Render each citation as its own individually-clickable badge
  if (items.length > 1) {
    return (
      <span className="inline-flex items-baseline gap-0.5 mx-0.5 align-baseline">
        {items.map((item, i) => (
          <CitationSingleBadge
            key={`${item.index}-${item.fileName}-${i}`}
            item={item}
            onViewPdf={onViewPdf}
          />
        ))}
      </span>
    );
  }

  return <CitationSingleBadge item={items[0]} onViewPdf={onViewPdf} />;
};
