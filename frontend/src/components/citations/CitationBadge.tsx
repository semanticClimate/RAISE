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
    const origin = typeof window !== 'undefined' && window.location?.origin ? window.location.origin : 'http://localhost';
    const parsed = new URL(trimmed, origin);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' || parsed.protocol === 'blob:';
  } catch {
    return false;
  }
}

export function resolveCitationDetail(cit?: Citation, fallbackIndex: number = 1): CitationItemDetail {
  const pageNumber = extractVerifiedPageNumber(cit);
  const citRecord = cit && typeof cit === 'object' ? (cit as Record<string, unknown>) : null;
  const citMeta = citRecord?.metadata && typeof citRecord.metadata === 'object' ? (citRecord.metadata as Record<string, unknown>) : null;

  const rawFileNameCand = cit?.pdf_filename || citRecord?.filename || citRecord?.file_name || citRecord?.document_name || citRecord?.doc_name || citRecord?.source || citMeta?.pdf_filename || citMeta?.filename;
  let rawFileName = typeof rawFileNameCand === 'string' ? rawFileNameCand.trim() : undefined;

  const rawUrlCand = cit?.url || citRecord?.url || citMeta?.url;
  const rawUrl = typeof rawUrlCand === 'string' ? rawUrlCand.trim() : undefined;
  const srcTypeCand = cit?.source_type || citRecord?.source_type || citMeta?.source_type;
  const sourceType = typeof srcTypeCand === 'string' ? srcTypeCand : undefined;

  const isWeb = sourceType === 'EXTERNAL_PUBLIC_RECORD' || sourceType === 'web' || Boolean(rawUrl && (rawUrl.startsWith('http://') || rawUrl.startsWith('https://'))) || Boolean(rawFileName && (rawFileName.startsWith('http://') || rawFileName.startsWith('https://')));

  let webUrl: string | undefined;
  if (isWeb) {
    const candidate = rawUrl || rawFileName;
    if (isSafeHttpUrl(candidate)) webUrl = candidate;
  }

  let fileName: string;
  if (isWeb) {
    if (cit?.heading && cit.heading.trim().length > 0) {
      fileName = cit.heading.trim();
    } else if (webUrl) {
      try {
        const u = new URL(webUrl);
        const lastPart = u.pathname.split('/').filter(Boolean).pop();
        fileName = lastPart ? decodeURIComponent(lastPart).replace(/_/g, ' ') : u.hostname;
      } catch {
        fileName = 'Public Web Source';
      }
    } else {
      fileName = 'Public Web Record';
    }
  } else {
    if (rawFileName) {
      const lastSlash = Math.max(rawFileName.lastIndexOf('/'), rawFileName.lastIndexOf('\\'));
      if (lastSlash >= 0) rawFileName = rawFileName.slice(lastSlash + 1).trim();
    }
    if (!rawFileName || rawFileName === 'Document' || rawFileName === 'Audited Document') {
      const chunkCand = cit?.chunk_id || citRecord?.id || citMeta?.chunk_id;
      if (typeof chunkCand === 'string') {
        const stemMatch = chunkCand.match(/^([a-zA-Z0-9_\-\s]+?)(?:_p\d+|_parent|\.pdf|$)/i);
        if (stemMatch?.[1] && stemMatch[1].length > 3 && !stemMatch[1].startsWith('chk_') && !stemMatch[1].startsWith('cit-')) {
          rawFileName = stemMatch[1].endsWith('.pdf') ? stemMatch[1] : `${stemMatch[1]}.pdf`;
        }
      }
    }
    fileName = rawFileName || 'Audited Document';
  }

  const base = getApiBaseUrl().replace(/\/+$/, '');
  const safePage = pageNumber && pageNumber > 0 ? pageNumber : 1;
  const toAbs = (p?: string | null) => (p ? `${base}${p.startsWith('/') ? '' : '/'}${p}` : undefined);

  const singlePagePdfUrl = isWeb ? undefined : toAbs(cit?.page_url) || (rawFileName ? sourceService.getSinglePagePdfUrl(rawFileName, safePage) : undefined);
  const singlePageImageUrl = isWeb ? undefined : toAbs(cit?.page_image_url) || (rawFileName ? sourceService.getSinglePageImageUrl(rawFileName, safePage) : undefined);
  const singlePageViewUrl = isWeb ? undefined : toAbs(cit?.page_view_url) || (rawFileName ? sourceService.getSinglePageViewUrl(rawFileName, safePage) : undefined);
  const pdfUrl = isWeb ? undefined : rawFileName ? sourceService.getPdfUrl(rawFileName, pageNumber) : undefined;

  const candidatePrimaryUrl = isWeb && webUrl ? webUrl : (pageNumber && pageNumber > 0 ? singlePageViewUrl || singlePagePdfUrl : undefined) || pdfUrl;
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
    plainText: cit?.plain_text || (cit as any)?.snippet,
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
    leaveTimeoutRef.current = setTimeout(() => setShowTooltip(false), 180);
  };

  useEffect(() => {
    return () => {
      if (leaveTimeoutRef.current) clearTimeout(leaveTimeoutRef.current);
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
    const target = item.isWeb ? item.webUrl || item.primaryUrl : item.singlePageViewUrl || item.singlePagePdfUrl || item.pdfUrl;
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
        title={item.isWeb ? `Click to open external web article: ${item.fileName}` : `Click to open ${item.fileName}${item.pageNumber ? ` at Page ${item.pageNumber}` : ''} in a new tab`}
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
          <Globe className="w-2.5 h-2.5 ml-0.5 opacity-70 group-hover:opacity-100 transition-opacity text-cyan-600 dark:text-cyan-400" />
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
          <div className="flex items-center justify-between gap-1.5 pb-1.5 border-b border-white/10">
            <div
              onClick={handleOpenFullPdfFromDiv}
              className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-100 hover:text-cyan-300 transition-colors cursor-pointer min-w-0"
              title={item.isWeb ? 'Click to open web record in new tab' : 'Click to open full PDF document in new tab'}
            >
              {item.isWeb ? <Globe className="w-3.5 h-3.5 shrink-0 text-cyan-400" /> : <FileText className="w-3.5 h-3.5 shrink-0 text-blue-400" />}
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

          {item.heading && (
            <div className="text-[11px] font-medium text-slate-300 mt-2 line-clamp-1 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
              <span className="truncate">{item.heading}</span>
            </div>
          )}

          {item.plainText && (
            <blockquote className="text-[10.5px] leading-relaxed text-slate-300 line-clamp-3 mt-1.5 italic bg-white/[0.04] p-2 rounded-lg border-l-2 border-cyan-500">
              "{item.plainText}"
            </blockquote>
          )}

          <div className="pt-2 mt-2 border-t border-white/10">
            {item.isWeb ? (
              <a
                href={item.primaryUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleClick}
                className="w-full inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-[10.5px] font-medium font-sans bg-cyan-600 hover:bg-cyan-500 text-white rounded-md shadow-2xs hover:scale-[1.01] active:scale-95 transition-all text-center cursor-pointer no-underline"
                title="Open public web record in new tab"
              >
                <Globe className="w-3 h-3" />
                <span>🌐 Open Public Record</span>
                <ExternalLink className="w-2.5 h-2.5 opacity-80" />
              </a>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
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
              </div>
            )}
          </div>

          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-950 pointer-events-none" />
        </div>
      )}
    </span>
  );
};

export const CitationBadge: React.FC<CitationBadgeProps> = ({ index, indices, citation, citations, onViewPdf }) => {
  const rawList = citations && citations.length > 0
    ? citations.map((c, i) => ({ cit: c, idx: indices?.[i] ?? c.citation_index ?? (index ? index + i : i + 1) }))
    : indices && indices.length > 0
      ? indices.map((idx) => ({ cit: citation, idx }))
      : [{ cit: citation, idx: index ?? 1 }];

  const items: CitationItemDetail[] = rawList.map((item) => resolveCitationDetail(item.cit, item.idx));

  if (items.length === 0) return null;

  if (items.length > 1) {
    return (
      <span className="inline-flex items-baseline gap-0.5 mx-0.5 align-baseline">
        {items.map((item, i) => (
          <CitationSingleBadge key={`${item.index}-${item.fileName}-${i}`} item={item} onViewPdf={onViewPdf} />
        ))}
      </span>
    );
  }

  return <CitationSingleBadge item={items[0]} onViewPdf={onViewPdf} />;
};
