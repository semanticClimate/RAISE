import { BookOpen, Check, Copy, Sparkles } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import type { Citation } from '../../types';
import { sourceService } from '../../services/SourceService';
import { cleanRagResponseText } from '../../utils/citationParser';
import { sanitizeStreamText } from '../../utils/sanitizeStreamText';
import { copyMarkdownToClipboard, splitTableRow } from '../../utils/exportFormats';
import { formatTableAsMarkdown } from '../../utils/tableFormatter';
import { CitationBadge, resolveCitationDetail } from '../citations/CitationBadge';
import { ComparabilityBadge, isComparabilityStatus } from './ComparabilityBadge';
import { KaTexRenderer } from './KaTexRenderer';

export interface AnswerMarkdownProps {
  content: string;
  citations?: Citation[];
  showCitations?: boolean;
  className?: string;
  onViewPdf?: (fileName: string, page: number, mode?: 'page' | 'full' | 'view') => void;
}

interface CodeBlockProps {
  code: string;
  language?: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="my-3.5 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 shadow-2xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-800/80 border-b border-slate-700/60 text-[11px] font-mono text-slate-400">
        <span className="font-medium tracking-wide uppercase">{language || 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? 'Copied code' : 'Copy code'}
          title={copied ? 'Copied!' : 'Copy code'}
          className="flex items-center justify-center p-1.5 rounded-md text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700/60 active:scale-95 transition-all cursor-pointer"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Copy className="w-3.5 h-3.5 text-slate-400 hover:text-white" />
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-[12.5px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
};

interface TableBlockProps {
  headers: string[];
  alignments: string[];
  rows: string[][];
  tableIdx: number;
  renderInline: (text: string, keyPrefix: string) => React.ReactNode;
}

const TableBlock: React.FC<TableBlockProps> = ({
  headers,
  alignments,
  rows,
  tableIdx,
  renderInline,
}) => {
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const markdown = formatTableAsMarkdown(headers, alignments, rows);
    if (!markdown) return;

    let success = false;
    try {
      success = await copyMarkdownToClipboard(markdown);
    } catch {
      success = false;
    }

    if (success) {
      setCopied(true);
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
      copyTimeoutRef.current = setTimeout(() => {
        setCopied(false);
      }, 2000);
    }
  };

  return (
    <div className="relative group/table my-4 rounded-xl border border-slate-200/90 dark:border-white/10 bg-white dark:bg-slate-900/50 shadow-xs">
      {/* ChatGPT-style dedicated copy button in top-right corner */}
      <div className="absolute top-2.5 right-2.5 z-20">
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? 'Copied table' : 'Copy table'}
          title={copied ? 'Copied!' : 'Copy table'}
          className="flex items-center justify-center p-1.5 rounded-md text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white bg-white/95 dark:bg-slate-800/95 hover:bg-slate-100 dark:hover:bg-slate-700/80 border border-slate-200/90 dark:border-slate-700/80 shadow-2xs backdrop-blur-xs active:scale-95 transition-all cursor-pointer select-none opacity-80 hover:opacity-100 group-hover/table:opacity-100 focus:opacity-100"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Copy className="w-3.5 h-3.5 text-slate-400 hover:text-white" />
          )}
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700">
        <table className="w-full min-w-[640px] text-left text-xs sm:text-sm border-collapse">
          <thead className="sticky top-0 z-10 bg-slate-100/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200 dark:border-white/10 text-slate-800 dark:text-slate-200 font-semibold shadow-xs">
            <tr>
              {headers.map((h, hIdx) => (
                <th
                  key={hIdx}
                  className={`sticky top-0 z-10 bg-slate-100/95 dark:bg-slate-900/95 backdrop-blur-md px-4 py-2.5 font-semibold text-slate-900 dark:text-slate-100 whitespace-nowrap text-xs sm:text-sm tracking-tight ${
                    alignments[hIdx] || 'text-left'
                  } ${hIdx === headers.length - 1 ? 'pr-20' : ''}`}
                >
                  {renderInline(h, `th-${tableIdx}-${hIdx}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {rows.map((row, rIdx) => (
              <tr
                key={rIdx}
                className="hover:bg-slate-50/80 dark:hover:bg-white/[0.04] even:bg-slate-50/30 dark:even:bg-white/[0.015] transition-colors"
              >
                {row.map((cell, cIdx) => {
                  const trimmedCell = cell.trim();
                  if (isComparabilityStatus(trimmedCell)) {
                    return (
                      <td
                        key={cIdx}
                        className={`px-4 py-2.5 text-slate-700 dark:text-slate-300 whitespace-nowrap ${
                          alignments[cIdx] || 'text-left'
                        }`}
                      >
                        <ComparabilityBadge status={trimmedCell} />
                      </td>
                    );
                  }
                  return (
                    <td
                      key={cIdx}
                      className={`px-4 py-2.5 text-slate-700 dark:text-slate-300 whitespace-nowrap ${
                        alignments[cIdx] || 'text-left'
                      }`}
                    >
                      {renderInline(cell, `td-${tableIdx}-${rIdx}-${cIdx}`)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

type Block =
  | { type: 'heading'; level: 1 | 2 | 3 | 4; text: string }
  | { type: 'code'; language: string; code: string }
  | { type: 'math'; formula: string }
  | { type: 'table'; headers: string[]; alignments: string[]; rows: string[][] }
  | { type: 'blockquote'; text: string }
  | { type: 'ordered-list'; items: { num: string; text: string; indent: number }[] }
  | { type: 'unordered-list'; items: { text: string; indent: number }[] }
  | { type: 'hr' }
  | { type: 'callout'; variant: 'info' | 'warning'; text: string }
  | { type: 'paragraph'; text: string };

function parseMarkdownBlocks(text: string): Block[] {
  const lines = text.split('\n');
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Empty lines
    if (!trimmed) {
      i++;
      continue;
    }

    // 2. Fenced Code Block: ```lang
    if (trimmed.startsWith('```')) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].trim().startsWith('```')) {
        i++;
      }
      blocks.push({
        type: 'code',
        language,
        code: codeLines.join('\n'),
      });
      continue;
    }

    // 2.5 LaTeX Block Math: $$ formula $$
    if (trimmed.startsWith('$$')) {
      if (trimmed.length > 4 && trimmed.endsWith('$$')) {
        blocks.push({
          type: 'math',
          formula: trimmed.slice(2, -2).trim(),
        });
        i++;
        continue;
      }
      const mathLines: string[] = [];
      if (trimmed.length > 2) {
        mathLines.push(trimmed.slice(2));
      }
      i++;
      while (i < lines.length && !lines[i].trim().endsWith('$$') && lines[i].trim() !== '$$') {
        mathLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) {
        const lastLine = lines[i].trim();
        if (lastLine !== '$$') {
          mathLines.push(lastLine.replace(/\$\$$/, ''));
        }
        i++;
      }
      blocks.push({
        type: 'math',
        formula: mathLines.join('\n').trim(),
      });
      continue;
    }

    // 3. Horizontal Rule: ---, ***, ___
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' });
      i++;
      continue;
    }

    // 4. Headings: #, ##, ###, #### (or malformed bullets with headings like • ### or • **###)
    const cleanHeadingLine = trimmed.replace(/^[•*-]\s*(?:\*\*)?\s*(#{1,4})/, '$1');
    if (cleanHeadingLine.startsWith('#')) {
      const match = cleanHeadingLine.match(/^(#{1,4})\s+(.*)$/);
      if (match) {
        const level = match[1].length as 1 | 2 | 3 | 4;
        let headingText = match[2].trim();

        // Check if heading line had bold title attached to body text: e.g. "**Title**Body" or "**Title** Body"
        const boldSplit = headingText.match(/^\*\*([^*]+)\*\*(?:\s*)(.+)$/);
        if (boldSplit) {
          headingText = boldSplit[1].trim();
          const remainderText = boldSplit[2].trim();
          blocks.push({
            type: 'heading',
            level,
            text: headingText,
          });
          if (remainderText) {
            blocks.push({
              type: 'paragraph',
              text: remainderText,
            });
          }
          i++;
          continue;
        }

        // Check if heading runs directly into sentence words:
        // e.g. "Patent: Biomimetic Polymeric Nanoformulation for OsteosarcomaThe report highlights..."
        const sentenceSplit = headingText.match(
          /^([A-Z][^.\n]{4,85}?)(?:(?<=[a-z0-9])(?=[A-Z][a-z]+\s+(?:report|study|paper|findings|data|analysis|investigates|demonstrates|presents|highlights|reveals|shows|concludes|from|in|is|are|was|were|aims|focuses|describes))|(?:\.\s+))([\s\S]+)$/
        );
        if (sentenceSplit) {
          headingText = sentenceSplit[1].trim();
          const remainderText = sentenceSplit[2].trim();
          blocks.push({
            type: 'heading',
            level,
            text: headingText,
          });
          if (remainderText) {
            blocks.push({
              type: 'paragraph',
              text: remainderText,
            });
          }
          i++;
          continue;
        }

        // Strip wrapping or trailing asterisks like **Title** or Title**
        headingText = headingText.replace(/^\*+|\*+$/g, '').trim();
        blocks.push({
          type: 'heading',
          level,
          text: headingText,
        });
        i++;
        continue;
      }
    }

    // Standalone bold section header: **Section Title** or known section titles
    if (/^\*\*[^*\n]+\*\*$/.test(trimmed)) {
      const inner = trimmed.slice(2, -2).trim();
      if (!inner.endsWith('.') && inner.length < 80) {
        blocks.push({
          type: 'heading',
          level: 3,
          text: inner,
        });
        i++;
        continue;
      }
    }

    if (
      /^(Key Strategic Conclusions|Institutional Strategic Outcomes|Overarching Institutional Conclusions|Strategic Framework and Economic Targets)$/i.test(
        trimmed
      )
    ) {
      blocks.push({
        type: 'heading',
        level: 3,
        text: trimmed,
      });
      i++;
      continue;
    }

    // 5. Blockquote: > text
    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      blocks.push({
        type: 'blockquote',
        text: quoteLines.join(' '),
      });
      continue;
    }

    // 6. Markdown Table: starts with | and followed by separator
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim();
      if (/^\|?(\s*:?-+:?\s*\|)+\s*$/.test(nextLine)) {
        const headers = splitTableRow(trimmed);
        const alignSpecs = splitTableRow(nextLine);
        const alignments = alignSpecs.map((spec) => {
          if (spec.startsWith(':') && spec.endsWith(':')) return 'text-center';
          if (spec.endsWith(':')) return 'text-right';
          return 'text-left';
        });

        i += 2;
        const rows: string[][] = [];
        while (
          i < lines.length &&
          lines[i].trim().startsWith('|') &&
          lines[i].trim().endsWith('|')
        ) {
          const cells = splitTableRow(lines[i]);
          rows.push(cells);
          i++;
        }

        blocks.push({
          type: 'table',
          headers,
          alignments,
          rows,
        });
        continue;
      }
    }

    // 7. Ordered List: 1. item
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: { num: string; text: string; indent: number }[] = [];
      while (i < lines.length) {
        const currentLine = lines[i];
        if (!currentLine.trim()) {
          let nextIdx = i + 1;
          while (nextIdx < lines.length && !lines[nextIdx].trim()) {
            nextIdx++;
          }
          if (nextIdx < lines.length && /^\s*\d+\.\s+/.test(lines[nextIdx])) {
            i = nextIdx;
            continue;
          }
          break;
        }
        const match = currentLine.match(/^(\s*)(\d+)\.\s+(.*)$/);
        if (match) {
          const indent = Math.floor(match[1].length / 2);
          items.push({
            num: match[2],
            text: match[3],
            indent,
          });
          i++;
        } else if (
          items.length > 0 &&
          currentLine.trim() &&
          (currentLine.startsWith('   ') ||
            currentLine.startsWith('\t') ||
            currentLine.startsWith('  '))
        ) {
          items[items.length - 1].text += `\n${currentLine.trim()}`;
          i++;
        } else {
          break;
        }
      }
      blocks.push({
        type: 'ordered-list',
        items,
      });
      continue;
    }

    // 8. Unordered List: - item, * item, or • item
    if (/^\s*([*\-•])\s+/.test(line)) {
      const items: { text: string; indent: number }[] = [];
      while (i < lines.length) {
        const currentLine = lines[i];
        if (!currentLine.trim()) {
          let nextIdx = i + 1;
          while (nextIdx < lines.length && !lines[nextIdx].trim()) {
            nextIdx++;
          }
          if (nextIdx < lines.length && /^\s*([*\-•])\s+/.test(lines[nextIdx])) {
            i = nextIdx;
            continue;
          }
          break;
        }
        const match = currentLine.match(/^(\s*)([*\-•])\s+(.*)$/);
        if (match) {
          const indent = Math.floor(match[1].length / 2);
          items.push({
            text: match[3],
            indent,
          });
          i++;
        } else if (
          items.length > 0 &&
          currentLine.trim() &&
          (currentLine.startsWith('   ') ||
            currentLine.startsWith('\t') ||
            currentLine.startsWith('  '))
        ) {
          items[items.length - 1].text += `\n${currentLine.trim()}`;
          i++;
        } else {
          break;
        }
      }
      blocks.push({
        type: 'unordered-list',
        items,
      });
      continue;
    }

    // 9. Callouts
    if (/^\*\*(Warning|Caution|Alert|Important):\*\*/i.test(trimmed)) {
      blocks.push({
        type: 'callout',
        variant: 'warning',
        text: trimmed,
      });
      i++;
      continue;
    }

    if (/^\*\*(Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(trimmed)) {
      blocks.push({
        type: 'callout',
        variant: 'info',
        text: trimmed,
      });
      i++;
      continue;
    }

    // 10. Standard Paragraph: group contiguous non-blank lines
    const paraLines: string[] = [trimmed];
    i++;
    while (i < lines.length) {
      const nextLine = lines[i];
      const nextTrimmed = nextLine.trim();
      if (!nextTrimmed) break;
      if (
        nextTrimmed.startsWith('#') ||
        nextTrimmed.startsWith('```') ||
        nextTrimmed.startsWith('$$') ||
        nextTrimmed.startsWith('>') ||
        /^(-{3,}|\*{3,}|_{3,})$/.test(nextTrimmed) ||
        /^\s*\d+\.\s+/.test(nextLine) ||
        /^\s*([*\-•])\s+/.test(nextLine) ||
        (nextTrimmed.startsWith('|') && nextTrimmed.endsWith('|')) ||
        /^\*\*(Warning|Caution|Alert|Important|Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(
          nextTrimmed
        )
      ) {
        break;
      }
      paraLines.push(nextTrimmed);
      i++;
    }

    blocks.push({
      type: 'paragraph',
      text: paraLines.join('\n'),
    });
  }

  return blocks;
}

const AnswerMarkdownBase: React.FC<AnswerMarkdownProps> = ({
  content,
  citations = [],
  showCitations = false,
  className = '',
  onViewPdf,
}) => {
  if (!content) return null;

  // Sanitize any raw JSON token fragments or leaked stream tokens
  const sanitized = sanitizeStreamText(content);

  // Clean RAG artifacts, unpack verbose in-text citations, and normalize layout
  const { cleanText: preparedText, citations: enrichedCitations } = cleanRagResponseText(
    sanitized,
    citations
  );

  // If showCitations is false, strip bracketed markers like [1], [2], [1, 2] from the content
  const cleanContent = showCitations
    ? preparedText
    : preparedText.replace(/\s*\[\d+(?:\s*,\s*\d+)*\]/g, '');

  const citationMap = new Map<number, Citation>();
  if (showCitations && enrichedCitations) {
    for (const c of enrichedCitations) {
      citationMap.set(c.citation_index, c);
    }
  }

  const renderInline = (text: string, keyPrefix: string): React.ReactNode => {
    if (!text) return null;

    // Tokenize text into inline elements (including LaTeX inline math $...$ and hash router links)
    const regex =
      /(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|__[^_]+__|\[\d+(?:\s*,\s*\d+)*\]|\[([^\]]+)\]\((https?:\/\/[^\s)]+|[#/][^\s)]+)\)|\b(?:FULLY_COMPARABLE|CONDITIONALLY_COMPARABLE|CONTEXT_ADJUSTED|NOT_COMPARABLE|INSUFFICIENT_EVIDENCE|EXTERNAL_SUPPLEMENTED|EXTERNAL_PUBLIC_RECORD)\b|\*[^*\n]+\*|_[^_\n]+_|\$[^\$\n]+?\$)/g;

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
          <ComparabilityBadge
            key={`${keyPrefix}-cmp-${elementIdx++}`}
            status={matchedStr}
          />
        );
      }
      // Inline code
      else if (matchedStr.startsWith('`') && matchedStr.endsWith('`')) {
        const inner = matchedStr.slice(1, -1);
        if (isComparabilityStatus(inner)) {
          elements.push(
            <ComparabilityBadge
              key={`${keyPrefix}-cmp-${elementIdx++}`}
              status={inner}
            />
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
            {renderInline(inner, `${keyPrefix}-b-${elementIdx}`)}
          </strong>
        );
      }
      // Citation Badge (single [1] or multiple [1, 2])
      else if (showCitations && /^\[\d+(?:\s*,\s*\d+)*\]$/.test(matchedStr)) {
        const rawIndices = matchedStr
          .slice(1, -1)
          .split(',')
          .map((s) => parseInt(s.trim(), 10))
          .filter((n) => !Number.isNaN(n));

        const matchedCitations = rawIndices
          .map(
            (citIdx) =>
              citationMap.get(citIdx) ??
              (citIdx > 0 && enrichedCitations && citIdx <= enrichedCitations.length
                ? enrichedCitations[citIdx - 1]
                : undefined) ??
              // Fallback to primary citation if index was out-of-bounds (e.g. LLM outputs [2] when 1 citation is returned)
              (enrichedCitations && enrichedCitations.length > 0
                ? enrichedCitations[0]
                : citations && citations.length > 0
                  ? citations[0]
                  : undefined)
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
  };

  // Extract and format reasoning tokens inside <think>...</think>
  let thoughtText: string | null = null;
  let parsedContent = cleanContent;
  const thinkMatch = cleanContent.match(/<think>([\s\S]*?)(?:<\/think>|$)/i);
  if (thinkMatch) {
    thoughtText = thinkMatch[1].trim();
    parsedContent = cleanContent.replace(/<think>[\s\S]*?(?:<\/think>|$)/i, '').trim();
  }

  const blocks = parseMarkdownBlocks(parsedContent);

  return (
    <div
      className={`space-y-3 leading-relaxed text-slate-800 dark:text-slate-200 font-sans text-[15px] ${className}`}
    >
      {thoughtText && (
        <details className="mb-3.5 rounded-xl border border-slate-200/80 dark:border-white/10 bg-slate-50/60 dark:bg-white/[0.02] p-3 text-xs group">
          <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-400 select-none flex items-center gap-2 hover:text-slate-900 dark:hover:text-slate-200">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
            <span>Reasoning Chain</span>
            <span className="text-[10px] text-slate-400 group-open:hidden font-mono">(click to expand)</span>
          </summary>
          <div className="mt-2.5 pt-2.5 border-t border-slate-200/60 dark:border-white/5 font-mono text-[11.5px] leading-relaxed text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
            {thoughtText}
          </div>
        </details>
      )}
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'heading': {
            if (block.level === 1) {
              return (
                <h2
                  key={idx}
                  className="text-xl sm:text-2xl font-semibold tracking-tight text-slate-900 dark:text-white mt-6 mb-2.5 pb-2 border-b border-slate-200/80 dark:border-white/10"
                >
                  {renderInline(block.text, `h1-${idx}`)}
                </h2>
              );
            }
            if (block.level === 2) {
              return (
                <h3
                  key={idx}
                  className="text-lg sm:text-xl font-semibold tracking-tight text-slate-900 dark:text-white mt-5 mb-2"
                >
                  {renderInline(block.text, `h2-${idx}`)}
                </h3>
              );
            }
            if (block.level === 3) {
              return (
                <h4
                  key={idx}
                  className="text-[16.5px] font-semibold text-slate-900 dark:text-white mt-4.5 mb-1.5"
                >
                  {renderInline(block.text, `h3-${idx}`)}
                </h4>
              );
            }
            return (
              <h5
                key={idx}
                className="text-[15px] font-semibold text-slate-900 dark:text-slate-200 mt-3.5 mb-1"
              >
                {renderInline(block.text, `h4-${idx}`)}
              </h5>
            );
          }

          case 'ordered-list': {
            return (
              <ol
                key={idx}
                className="my-3 pl-6 list-decimal space-y-1.5 text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 marker:text-slate-500 dark:marker:text-slate-400 marker:font-medium"
              >
                {block.items.map((item, itemIdx) => (
                  <li
                    key={itemIdx}
                    className={`pl-1 leading-[1.75] ${item.indent > 0 ? 'ml-4' : ''}`}
                  >
                    {renderInline(item.text, `ol-${idx}-${itemIdx}`)}
                  </li>
                ))}
              </ol>
            );
          }

          case 'unordered-list': {
            return (
              <ul
                key={idx}
                className="my-3 pl-6 list-disc space-y-1.5 text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 marker:text-slate-400 dark:marker:text-slate-500"
              >
                {block.items.map((item, itemIdx) => {
                  const boldKeyMatch = item.text.match(/^(\*\*[^*]+\*\*:?)\s*([\s\S]*)$/);

                  if (boldKeyMatch) {
                    const cleanKey = boldKeyMatch[1]
                      .replace(/^\*\*|\*\*$/g, '')
                      .replace(/:$/, '')
                      .trim();
                    const value = boldKeyMatch[2].trim();
                    return (
                      <li
                        key={itemIdx}
                        className={`pl-1 leading-[1.75] ${
                          item.indent > 0 ? 'ml-4 list-[circle]' : ''
                        }`}
                      >
                        <strong className="font-semibold text-slate-900 dark:text-white mr-1.5">
                          {cleanKey}:
                        </strong>
                        {value && (
                          <span className="text-slate-800 dark:text-slate-200">
                            {renderInline(value, `ul-v-${idx}-${itemIdx}`)}
                          </span>
                        )}
                      </li>
                    );
                  }

                  return (
                    <li
                      key={itemIdx}
                      className={`pl-1 leading-[1.75] ${
                        item.indent > 0 ? 'ml-4 list-[circle]' : ''
                      }`}
                    >
                      {renderInline(item.text, `ul-${idx}-${itemIdx}`)}
                    </li>
                  );
                })}
              </ul>
            );
          }

          case 'blockquote': {
            return (
              <blockquote
                key={idx}
                className="border-l-2 border-slate-300 dark:border-slate-700 pl-3.5 py-1.5 my-3 bg-slate-50/70 dark:bg-white/[0.02] rounded-r-lg text-slate-600 dark:text-slate-300 italic text-[14px] leading-relaxed"
              >
                {renderInline(block.text, `bq-${idx}`)}
              </blockquote>
            );
          }

          case 'callout': {
            if (block.variant === 'warning') {
              return (
                <div
                  key={idx}
                  className="my-3 p-3.5 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/60 text-slate-800 dark:text-slate-200 text-[14px] leading-relaxed flex items-start gap-2.5"
                >
                  <span className="text-amber-600 dark:text-amber-400 font-bold shrink-0 mt-0.5">
                    ⚠
                  </span>
                  <div className="flex-1 min-w-0">
                    {renderInline(block.text, `callout-warn-${idx}`)}
                  </div>
                </div>
              );
            }
            return (
              <div
                key={idx}
                className="my-3 p-3.5 rounded-xl bg-slate-100/70 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/10 text-slate-800 dark:text-slate-200 text-[14px] leading-relaxed flex items-start gap-2.5"
              >
                <span className="text-slate-500 dark:text-slate-400 font-bold shrink-0 mt-0.5">
                  ℹ
                </span>
                <div className="flex-1 min-w-0">
                  {renderInline(block.text, `callout-info-${idx}`)}
                </div>
              </div>
            );
          }

          case 'math': {
            return (
              <KaTexRenderer
                key={idx}
                formula={block.formula}
                displayMode={true}
              />
            );
          }

          case 'code': {
            return <CodeBlock key={idx} code={block.code} language={block.language} />;
          }

          case 'table': {
            return (
              <TableBlock
                key={idx}
                tableIdx={idx}
                headers={block.headers}
                alignments={block.alignments}
                rows={block.rows}
                renderInline={renderInline}
              />
            );
          }

          case 'hr': {
            return (
              <hr key={idx} className="my-5 border-t border-slate-200/80 dark:border-white/10" />
            );
          }

          default: {
            return (
              <p
                key={idx}
                className="text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 my-2.5 whitespace-pre-line"
              >
                {renderInline(block.text, `p-${idx}`)}
              </p>
            );
          }
        }
      })}

      {/* Vertical Sources list */}
      {showCitations && enrichedCitations && enrichedCitations.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-white/5 flex flex-col gap-2 text-xs text-slate-500 dark:text-slate-400 select-text">
          <div className="flex items-center gap-1.5 font-medium text-slate-400 dark:text-slate-500 text-[11px] tracking-wide uppercase shrink-0">
            <BookOpen className="w-3.5 h-3.5 text-blue-500" />
            <span>Sources:</span>
          </div>

          <div className="flex flex-wrap gap-2 pt-0.5 min-w-0">
            {enrichedCitations.map((cit, citIdx) => {
              const detail = resolveCitationDetail(cit, citIdx + 1);
              const targetUrl = detail.isWeb
                ? (detail.webUrl || detail.primaryUrl)
                : sourceService.getPdfUrl(detail.fileName, detail.pageNumber || 1);

              return (
                <a
                  key={`${detail.index}-${detail.fileName}-${citIdx}`}
                  href={targetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    e.stopPropagation();
                    // Open directly in a new browser tab, never as an in-page popup modal
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

export const AnswerMarkdown = React.memo(AnswerMarkdownBase);
