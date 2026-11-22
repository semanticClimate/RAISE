import { Check, Copy } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { copyMarkdownToClipboard } from '../../../utils/exportFormats';
import { formatTableAsMarkdown } from '../../../utils/tableFormatter';
import { ComparabilityBadge, isComparabilityStatus } from '../ComparabilityBadge';
import { ComparativeDiffGrid, isComparativeTable } from './ComparativeDiffGrid';

export interface TableBlockProps {
  headers: string[];
  alignments: string[];
  rows: string[][];
  tableIdx: number;
  renderInline: (text: string, keyPrefix: string) => React.ReactNode;
}

export const TableBlock: React.FC<TableBlockProps> = ({
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

  // Dedicated Comparative Diff Grid view for comparative institutional reports & /compare outputs
  if (isComparativeTable(headers, rows)) {
    return (
      <ComparativeDiffGrid
        headers={headers}
        alignments={alignments}
        rows={rows}
        tableIdx={tableIdx}
        renderInline={renderInline}
      />
    );
  }

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
