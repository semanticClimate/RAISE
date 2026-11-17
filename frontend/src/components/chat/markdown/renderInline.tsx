import React from 'react';
import type { Citation } from '../../../types';
import { CitationBadge } from '../../citations/CitationBadge';
import { ComparabilityBadge, isComparabilityStatus } from '../ComparabilityBadge';
import { KaTexRenderer } from '../KaTexRenderer';

// Static hoisted RegExp to prevent regex engine recompilation on every inline render
export const INLINE_MARKDOWN_REGEX =
  /(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|__[^_]+__|\[\d+(?:\s*,\s*\d+)*\]|\[([^\]]+)\]\((https?:\/\/[^\s)]+|[#/][^\s)]+)\)|\b(?:FULLY_COMPARABLE|CONDITIONALLY_COMPARABLE|CONTEXT_ADJUSTED|NOT_COMPARABLE|INSUFFICIENT_EVIDENCE|EXTERNAL_SUPPLEMENTED|EXTERNAL_PUBLIC_RECORD)\b|\*[^*\n]+\*|_[^_\n]+_|\$[^\$\n]+?\$)/g;

export interface RenderInlineOptions {
  showCitations?: boolean;
  citationMap: Map<number, Citation>;
  enrichedCitations: Citation[];
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
}

export function renderInlineContent(
  text: string,
  keyPrefix: string,
  options: RenderInlineOptions
): React.ReactNode {
  if (!text) return null;

  const { showCitations, citationMap, enrichedCitations, onViewPdf } = options;
  const regex = new RegExp(INLINE_MARKDOWN_REGEX.source, 'g');
  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match = regex.exec(text);
  let elementIdx = 0;

  while (match !== null) {
    const matchStart = match.index;
    const matchEnd = regex.lastIndex;
    const matchedStr = match[0];

    if (matchStart > lastIndex) {
      elements.push(
        <span key={`${keyPrefix}-txt-${elementIdx++}`}>
          {text.substring(lastIndex, matchStart)}
        </span>
      );
    }

    // Comparability Status pill
    if (isComparabilityStatus(matchedStr)) {
      elements.push(
        <ComparabilityBadge key={`${keyPrefix}-cmp-${elementIdx++}`} status={matchedStr} />
      );
    }
    // Inline code
    else if (matchedStr.startsWith('`') && matchedStr.endsWith('`')) {
      const inner = matchedStr.slice(1, -1);
      if (isComparabilityStatus(inner)) {
        elements.push(
          <ComparabilityBadge key={`${keyPrefix}-cmp-${elementIdx++}`} status={inner} />
        );
      } else {
        elements.push(
          <code
            key={`${keyPrefix}-code-${elementIdx++}`}
            className="px-1.5 py-0.5 mx-0.5 rounded-md bg-slate-100 dark:bg-white/[0.08] text-slate-800 dark:text-slate-200 font-mono text-[12.5px] border border-slate-200/80 dark:border-white/10"
          >
            {inner}
          </code>
        );
      }
    }
    // Bold Italic
    else if (matchedStr.startsWith('***') && matchedStr.endsWith('***')) {
      elements.push(
        <strong
          key={`${keyPrefix}-bi-${elementIdx++}`}
          className="font-bold italic text-slate-900 dark:text-white"
        >
          {matchedStr.slice(3, -3)}
        </strong>
      );
    }
    // Bold
    else if (
      (matchedStr.startsWith('**') && matchedStr.endsWith('**')) ||
      (matchedStr.startsWith('__') && matchedStr.endsWith('__'))
    ) {
      const inner = matchedStr.slice(2, -2);
      elements.push(
        <strong
          key={`${keyPrefix}-b-${elementIdx++}`}
          className="font-semibold text-slate-900 dark:text-white"
        >
          {renderInlineContent(inner, `${keyPrefix}-b-${elementIdx}`, options)}
        </strong>
      );
    }
    // Citation Badge (single [1] or multiple [1, 2])
    else if (showCitations && /^\[\d+(?:\s*,\s*\d+)*\]$/.test(matchedStr)) {
      const rawIndices = matchedStr
        .slice(1, -1)
        .split(',')
        .map((s) => Number.parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));

      const matchedCitations = rawIndices
        .map(
          (citIdx) =>
            citationMap.get(citIdx) ??
            (citIdx > 0 && enrichedCitations && citIdx <= enrichedCitations.length
              ? enrichedCitations[citIdx - 1]
              : undefined) ??
            (enrichedCitations && enrichedCitations.length > 0 ? enrichedCitations[0] : undefined)
        )
        .filter(Boolean) as Citation[];

      elements.push(
        <CitationBadge
          key={`${keyPrefix}-cit-${elementIdx++}`}
          indices={rawIndices}
          citations={matchedCitations}
          index={rawIndices[0]}
          citation={matchedCitations[0]}
          onViewPdf={onViewPdf}
        />
      );
    }
    // Link
    else if (match[2] && match[3]) {
      elements.push(
        <a
          key={`${keyPrefix}-link-${elementIdx++}`}
          href={match[3]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-900 dark:text-white underline underline-offset-2 hover:opacity-80 font-medium inline-flex items-center gap-0.5"
        >
          {match[2]}
        </a>
      );
    }
    // Italic
    else if (
      (matchedStr.startsWith('*') && matchedStr.endsWith('*')) ||
      (matchedStr.startsWith('_') && matchedStr.endsWith('_'))
    ) {
      elements.push(
        <em
          key={`${keyPrefix}-em-${elementIdx++}`}
          className="italic text-slate-700 dark:text-slate-300"
        >
          {matchedStr.slice(1, -1)}
        </em>
      );
    }
    // Inline math: $formula$
    else if (matchedStr.startsWith('$') && matchedStr.endsWith('$') && matchedStr.length > 2) {
      const formula = matchedStr.slice(1, -1).trim();
      elements.push(
        <KaTexRenderer
          key={`${keyPrefix}-math-${elementIdx++}`}
          formula={formula}
          displayMode={false}
        />
      );
    } else {
      elements.push(<span key={`${keyPrefix}-raw-${elementIdx++}`}>{matchedStr}</span>);
    }

    lastIndex = matchEnd;
    match = regex.exec(text);
  }

  if (lastIndex < text.length) {
    elements.push(
      <span key={`${keyPrefix}-txt-${elementIdx++}`}>{text.substring(lastIndex)}</span>
    );
  }

  return <React.Fragment key={keyPrefix}>{elements}</React.Fragment>;
}
