import type React from 'react';
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
  if (trimmed === '#' || trimmed.startsWith('javascript:')) return false;
  if (trimmed.startsWith('#/')) return true;
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

  // Sid says: Primary URL points to external web URL for web records or direct browser PDF viewer
  const candidatePrimaryUrl =
    (isWeb && webUrl
      ? webUrl
      : pdfUrl ||
        (rawFileName
          ? sourceService.getPdfUrl(rawFileName, safePage)
          : undefined) ||
        singlePageViewUrl);

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
  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.stopPropagation();
    // Sid says: Open directly in a new browser tab, never as an in-page popup modal
    if (!item.isWeb && onViewPdf && item.fileName && item.fileName !== 'Audited Document') {
      e.preventDefault();
      onViewPdf(item.fileName, item.pageNumber || 1, 'page');
      return;
    }
    const target = item.isWeb ? item.webUrl || item.primaryUrl : item.primaryUrl;
    if (target && target !== '#' && isSafeUrl(target) && typeof window !== 'undefined') {
      e.preventDefault();
      window.open(target, '_blank', 'noopener,noreferrer');
    }
  };

  const tooltipLabel = item.isWeb
    ? item.fileName
    : `${item.fileName}${item.pageNumber !== undefined && item.pageNumber > 0 ? ` (p. ${item.pageNumber})` : ''}`;

  return (
    <span className="relative inline-block mx-0.5 align-baseline">
      <a
        href={item.primaryUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={handleClick}
        title={tooltipLabel}
        aria-label={`Citation [${item.index}]: ${tooltipLabel}`}
        className="inline font-mono text-xs font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] transition-all cursor-pointer select-none no-underline"
      >
        <span>[{item.index}]</span>
      </a>
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
