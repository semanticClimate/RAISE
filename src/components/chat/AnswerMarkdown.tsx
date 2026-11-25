import { BookOpen, Sparkles } from 'lucide-react';
import React, { useMemo } from 'react';
import type { Citation } from '../../types';
import { sourceService } from '../../services/SourceService';
import { cleanRagResponseText } from '../../utils/citationParser';
import { extractReasoningAndAnswer } from '../../utils/reasoningParser';
import { sanitizeStreamText } from '../../utils/sanitizeStreamText';
import { resolveCitationDetail } from '../citations/CitationBadge';
import { MemoizedMarkdownBlock } from './markdown/MemoizedMarkdownBlock';
import { parseMarkdownBlocks } from './markdown/markdownParser';
import type { RenderInlineOptions } from './markdown/renderInline';

export interface AnswerMarkdownProps {
  content: string;
  citations?: Citation[];
  showCitations?: boolean;
  isStreaming?: boolean;
  className?: string;
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
}

const AnswerMarkdownBase: React.FC<AnswerMarkdownProps> = ({
  content,
  citations = [],
  showCitations = false,
  isStreaming = false,
  className = '',
  onViewPdf,
}) => {
  // 1. Sanitize any raw JSON token fragments or leaked stream tokens (all hooks stay unconditional)
  const sanitized = useMemo(() => (content ? sanitizeStreamText(content) : ''), [content]);

  // 2. Extract <think>...</think> reasoning and rescue conclusions BEFORE citation formatting runs
  const { thoughtText, answerText, isStreamingThought, rescuedFromThought } = useMemo(
    () => extractReasoningAndAnswer(sanitized, { isStreaming }),
    [sanitized, isStreaming]
  );

  // While streaming an unclosed reasoning trace, surface live tokens immediately instead of a closed box
  const activeMarkdownSource = isStreamingThought ? thoughtText || '' : answerText;

  // 3. Clean RAG artifacts, unpack verbose in-text citations, and normalize layout on the answer body
  const { cleanText: preparedText, citations: enrichedCitations } = useMemo(
    () => cleanRagResponseText(activeMarkdownSource, citations, { preserveReasoningTags: true }),
    [activeMarkdownSource, citations]
  );

  const displayCitations = useMemo(
    () => (enrichedCitations && enrichedCitations.length > 0 ? enrichedCitations : citations || []),
    [enrichedCitations, citations]
  );

  // 4. If showCitations is false, strip bracketed markers like [1], [2], [1, 2] from the content
  const cleanContent = useMemo(
    () =>
      showCitations ? preparedText : preparedText.replace(/\s*\[\d+(?:\s*,\s*\d+)*\]/g, ''),
    [showCitations, preparedText]
  );

  // 5. Citation lookup map by citation_index
  const citationMap = useMemo(() => {
    const map = new Map<number, Citation>();
    if (showCitations && displayCitations) {
      for (const c of displayCitations) {
        map.set(c.citation_index, c);
      }
    }
    return map;
  }, [showCitations, displayCitations]);

  // 6. Parse structured markdown blocks (memoized to prevent re-tokenization)
  const blocks = useMemo(() => parseMarkdownBlocks(cleanContent), [cleanContent]);

  // 7. Stable inline options reference for MemoizedMarkdownBlock children
  const inlineOptions = useMemo<RenderInlineOptions>(
    () => ({
      showCitations,
      citationMap,
      enrichedCitations: displayCitations,
      onViewPdf,
    }),
    [showCitations, citationMap, displayCitations, onViewPdf]
  );

  if (!content || (!cleanContent && !thoughtText)) return null;

  return (
    <div
      className={`space-y-3 leading-relaxed text-slate-800 dark:text-slate-200 font-sans text-[15px] ${className}`}
    >
      {thoughtText && !isStreamingThought && (
        <details className="mb-3.5 rounded-xl border border-slate-200/80 dark:border-white/10 bg-slate-50/60 dark:bg-white/[0.02] p-3 text-xs group">
          <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-400 select-none flex items-center gap-2 hover:text-slate-900 dark:hover:text-slate-200">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" aria-hidden="true" />
            <span>Reasoning Chain</span>
            <span className="text-[10px] text-slate-400 group-open:hidden font-mono">
              (click to expand)
            </span>
          </summary>
          <div className="mt-2.5 pt-2.5 border-t border-slate-200/60 dark:border-white/5 font-mono text-[11.5px] leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
            {thoughtText}
          </div>
        </details>
      )}

      {(isStreamingThought || rescuedFromThought) && (
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-indigo-600/90 dark:text-indigo-400/90 select-none">
          <Sparkles
            className={`w-3.5 h-3.5 text-indigo-500${isStreamingThought ? ' animate-pulse' : ''}`}
            aria-hidden="true"
          />
          <span>Synthesized from model reasoning chain:</span>
        </div>
      )}

      {blocks.length > 0 ? (
        blocks.map((block, idx) => (
          <MemoizedMarkdownBlock
            key={idx}
            block={block}
            blockIdx={idx}
            inlineOptions={inlineOptions}
          />
        ))
      ) : isStreamingThought && thoughtText ? (
        <div className="text-sm leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
          {thoughtText}
        </div>
      ) : null}

      {/* Vertical Sources list */}
      {showCitations && displayCitations && displayCitations.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-white/5 flex flex-col gap-2 text-xs text-slate-500 dark:text-slate-400 select-text">
          <div className="flex items-center gap-1.5 font-medium text-slate-400 dark:text-slate-500 text-[11px] tracking-wide uppercase shrink-0">
            <BookOpen className="w-3.5 h-3.5 text-blue-500" aria-hidden="true" />
            <span>Sources:</span>
          </div>

          <div className="flex flex-wrap gap-2 pt-0.5 min-w-0">
            {displayCitations.map((cit, citIdx) => {
              const detail = resolveCitationDetail(cit, citIdx + 1);
              const targetUrl = detail.isWeb
                ? detail.webUrl || detail.primaryUrl
                : sourceService.getPdfUrl(detail.fileName, detail.pageNumber || 1);

              return (
                <a
                  key={`${detail.index}-${detail.fileName}-${citIdx}`}
                  href={targetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (
                      onViewPdf &&
                      detail.fileName &&
                      detail.fileName !== 'Audited Document' &&
                      !detail.isWeb
                    ) {
                      e.preventDefault();
                      onViewPdf(detail.fileName, detail.pageNumber || 1, 'page');
                      return;
                    }
                    if (typeof window !== 'undefined' && targetUrl && targetUrl !== '#') {
                      e.preventDefault();
                      window.open(targetUrl, '_blank', 'noopener,noreferrer');
                    }
                  }}
                  className="inline-flex items-center gap-1.5 py-1 px-2.5 rounded-xl bg-slate-100/80 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/10 hover:bg-slate-200/60 dark:hover:bg-white/[0.08] hover:border-blue-400 dark:hover:border-blue-500/50 text-[12px] text-slate-800 dark:text-slate-200 transition-all no-underline font-normal w-fit cursor-pointer shadow-2xs group/cit"
                  title={`${detail.fileName}${detail.pageNumber !== undefined && detail.pageNumber > 0 ? ` (p. ${detail.pageNumber})` : ''}`}
                >
                  <span className="font-mono font-semibold text-blue-600 dark:text-blue-400 shrink-0">
                    [{detail.index}]
                  </span>
                  <span className="truncate max-w-[280px] sm:max-w-none group-hover/cit:text-blue-600 dark:group-hover/cit:text-blue-400 transition-colors">
                    {detail.fileName}
                  </span>
                  {detail.pageNumber !== undefined && detail.pageNumber > 0 && (
                    <span className="text-slate-400 dark:text-slate-500 font-mono text-[11px] shrink-0">
                      (p. {detail.pageNumber})
                    </span>
                  )}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

function areAnswerMarkdownPropsEqual(
  prev: AnswerMarkdownProps,
  next: AnswerMarkdownProps
): boolean {
  if (prev.content !== next.content) return false;
  if (prev.showCitations !== next.showCitations) return false;
  if (prev.isStreaming !== next.isStreaming) return false;
  if (prev.className !== next.className) return false;
  if (prev.onViewPdf !== next.onViewPdf) return false;
  if ((prev.citations?.length || 0) !== (next.citations?.length || 0)) return false;
  if (prev.citations === next.citations) return true;

  // Cheap index/filename comparison to skip full deep equal
  const pCits = prev.citations || [];
  const nCits = next.citations || [];
  for (let i = 0; i < pCits.length; i++) {
    if (
      pCits[i].citation_index !== nCits[i].citation_index ||
      pCits[i].pdf_filename !== nCits[i].pdf_filename ||
      pCits[i].primary_page !== nCits[i].primary_page
    ) {
      return false;
    }
  }
  return true;
}

export const AnswerMarkdown = React.memo(AnswerMarkdownBase, areAnswerMarkdownPropsEqual);
