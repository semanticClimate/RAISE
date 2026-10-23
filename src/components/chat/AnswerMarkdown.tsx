import { BookOpen, ExternalLink, FileText } from 'lucide-react';
import React, { useState } from 'react';
import type { Citation } from '../../types';
import { cleanRagResponseText } from '../../utils/citationParser';
import { sanitizeStreamText } from '../../utils/sanitizeStreamText';
import { CitationBadge, resolveCitationDetail } from '../citations/CitationBadge';
import { ComparabilityBadge, isComparabilityStatus } from './ComparabilityBadge';

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
          className="text-xs text-slate-400 hover:text-white transition-colors cursor-pointer px-1.5 py-0.5 rounded hover:bg-slate-700/60"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-[12.5px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
};

type Block =
  | { type: 'heading'; level: 1 | 2 | 3 | 4; text: string }
  | { type: 'code'; language: string; code: string }
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
        const headers = trimmed
          .slice(1, -1)
          .split('|')
          .map((s) => s.trim());
        const alignSpecs = nextLine
          .slice(1, -1)
          .split('|')
          .map((s) => s.trim());
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
          const cells = lines[i]
            .trim()
            .slice(1, -1)
            .split('|')
            .map((s) => s.trim());
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

export const AnswerMarkdown: React.FC<AnswerMarkdownProps> = ({
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

    // Tokenize text into inline elements
    const regex =
      /(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|__[^_]+__|\[\d+(?:\s*,\s*\d+)*\]|\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]+)\)|\b(?:FULLY_COMPARABLE|CONDITIONALLY_COMPARABLE|CONTEXT_ADJUSTED|NOT_COMPARABLE|INSUFFICIENT_EVIDENCE|EXTERNAL_SUPPLEMENTED|EXTERNAL_PUBLIC_RECORD)\b|\*[^*\n]+\*|_[^_\n]+_)/g;

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

  const blocks = parseMarkdownBlocks(cleanContent);

  return (
    <div
      className={`space-y-3 leading-relaxed text-slate-800 dark:text-slate-200 font-sans text-[15px] ${className}`}
    >
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

          case 'code': {
            return <CodeBlock key={idx} code={block.code} language={block.language} />;
          }

          case 'table': {
            return (
              <div
                key={idx}
                className="overflow-x-auto my-4 rounded-xl border border-slate-200/80 dark:border-white/10 shadow-2xs scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700"
              >
                <table className="w-full min-w-[640px] text-left text-xs sm:text-sm border-collapse">
                  <thead className="bg-slate-100/80 dark:bg-white/[0.05] border-b border-slate-200 dark:border-white/10 text-slate-800 dark:text-slate-200 font-semibold">
                    <tr>
                      {block.headers.map((h, hIdx) => (
                        <th
                          key={hIdx}
                          className={`px-4 py-2.5 font-semibold text-slate-900 dark:text-slate-100 ${
                            block.alignments[hIdx] || 'text-left'
                          }`}
                        >
                          {renderInline(h, `th-${idx}-${hIdx}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {block.rows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className="hover:bg-slate-50/60 dark:hover:bg-white/[0.02] transition-colors"
                      >
                        {row.map((cell, cIdx) => {
                          const trimmedCell = cell.trim();
                          if (isComparabilityStatus(trimmedCell)) {
                            return (
                              <td
                                key={cIdx}
                                className={`px-4 py-2.5 text-slate-700 dark:text-slate-300 ${
                                  block.alignments[cIdx] || 'text-left'
                                }`}
                              >
                                <ComparabilityBadge status={trimmedCell} />
                              </td>
                            );
                          }
                          return (
                            <td
                              key={cIdx}
                              className={`px-4 py-2 text-slate-700 dark:text-slate-300 ${
                                block.alignments[cIdx] || 'text-left'
                              }`}
                            >
                              {renderInline(cell, `td-${idx}-${rIdx}-${cIdx}`)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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

      {/* Grounded Sources & Verified Citations Card */}
      {showCitations && enrichedCitations && enrichedCitations.length > 0 && (
        <div className="mt-6 pt-4 border-t border-slate-200/90 dark:border-white/10 select-text">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              <BookOpen className="w-3.5 h-3.5 text-blue-500" />
              <span>Sources ({enrichedCitations.length})</span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
              Click to view in new tab
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {enrichedCitations.map((cit, citIdx) => {
              const detail = resolveCitationDetail(cit, citIdx + 1);
              return (
                <div
                  key={`${detail.index}-${detail.fileName}-${citIdx}`}
                  className="p-3 rounded-xl bg-slate-50/90 dark:bg-white/[0.03] border border-slate-200/90 dark:border-white/10 hover:border-blue-400/60 dark:hover:border-blue-500/60 transition-all duration-150 flex flex-col justify-between group shadow-2xs"
                >
                  <div>
                    {/* Top row: badge + filename + page pill */}
                    <div className="flex items-start justify-between gap-1.5 mb-1.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="px-1.5 py-0.5 rounded text-[10.5px] font-mono font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 shrink-0">
                          [{detail.index}]
                        </span>
                        <div
                          className="flex items-center gap-1 text-[12px] font-semibold text-slate-800 dark:text-slate-200 truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors"
                          title={detail.fileName}
                        >
                          <FileText className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                          <span className="truncate">{detail.fileName}</span>
                        </div>
                      </div>

                      {detail.pageNumber !== undefined && detail.pageNumber > 0 && (
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60 shrink-0">
                          Page {detail.pageNumber}
                        </span>
                      )}
                    </div>

                    {/* Section heading */}
                    {detail.heading && (
                      <div className="text-[11px] font-medium text-slate-600 dark:text-slate-300 mb-1 line-clamp-1">
                        {detail.heading}
                      </div>
                    )}

                    {/* Excerpt */}
                    {detail.plainText && (
                      <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400 line-clamp-2 italic mb-2">
                        "{detail.plainText}"
                      </p>
                    )}
                  </div>

                  {/* Quick Action Buttons */}
                  <div className="flex items-center gap-2 pt-2 border-t border-slate-200/60 dark:border-white/5">
                    <a
                      href={detail.singlePageViewUrl || detail.singlePagePdfUrl || detail.pdfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (
                          onViewPdf &&
                          detail.fileName &&
                          detail.fileName !== 'Audited Document'
                        ) {
                          onViewPdf(detail.fileName, detail.pageNumber || 1, 'page');
                          return;
                        }
                        if (
                          detail.primaryUrl &&
                          detail.primaryUrl !== '#' &&
                          typeof window !== 'undefined'
                        ) {
                          window.open(detail.primaryUrl, '_blank', 'noopener,noreferrer');
                        }
                      }}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[10.5px] font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors cursor-pointer shadow-2xs no-underline"
                      title={`Open Page ${detail.pageNumber || 1} in a new tab`}
                    >
                      <span>⚡ Open Page {detail.pageNumber || 1}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>

                    {detail.pdfUrl && (
                      <a
                        href={detail.pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (
                            onViewPdf &&
                            detail.fileName &&
                            detail.fileName !== 'Audited Document'
                          ) {
                            onViewPdf(detail.fileName, detail.pageNumber || 1, 'full');
                            return;
                          }
                          if (typeof window !== 'undefined') {
                            window.open(detail.pdfUrl, '_blank', 'noopener,noreferrer');
                          }
                        }}
                        className="inline-flex items-center gap-1 px-2 py-1 text-[10.5px] font-medium bg-slate-200/80 hover:bg-slate-300/80 dark:bg-white/[0.08] dark:hover:bg-white/[0.14] text-slate-700 dark:text-slate-300 rounded-md transition-colors cursor-pointer no-underline"
                        title="Open full PDF document in a new tab"
                      >
                        <span>📖 Full PDF</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
