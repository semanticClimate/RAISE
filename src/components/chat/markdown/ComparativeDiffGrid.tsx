import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Columns,
  FileSpreadsheet,
  FileText,
  Minus,
  Search,
  Table as TableIcon,
} from 'lucide-react';
import React, { useId, useMemo, useRef, useState } from 'react';
import { copyMarkdownToClipboard } from '../../../utils/exportFormats';
import { formatTableAsMarkdown } from '../../../utils/tableFormatter';
import { ComparabilityBadge, isComparabilityStatus } from '../ComparabilityBadge';

export interface ComparativeDiffGridProps {
  headers: string[];
  alignments: string[];
  rows: string[][];
  tableIdx: number;
  renderInline: (text: string, keyPrefix: string) => React.ReactNode;
}

/**
 * Checks whether a Markdown table contains comparative institutional analysis.
 */
export function isComparativeTable(headers: string[], rows: string[][]): boolean {
  if (headers.length < 3) return false;

  const headerStr = headers.join(' ').toLowerCase();
  const comparativeKeywords = [
    'metric',
    'dimension',
    'indicator',
    'parameter',
    'feature',
    'focus',
    'aspect',
    'component',
    'report',
    'annual report',
    'nipgr',
    'bric',
    '2021',
    '2022',
    '2023',
    '2024',
    '2025',
    '2026',
    'compare',
    'comparison',
    'variance',
    'delta',
    'difference',
    'status',
    'comparability',
    'versus',
    'vs',
  ];

  const hasComparativeHeader = comparativeKeywords.some((kw) => headerStr.includes(kw));
  if (hasComparativeHeader) return true;

  // Check if any row cell matches known comparability status tokens
  for (const row of rows) {
    for (const cell of row) {
      if (isComparabilityStatus(cell.trim())) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Formats table rows into clean CSV format for spreadsheet export.
 */
function formatTableAsCsv(headers: string[], rows: string[][]): string {
  const escapeCell = (c: string) => {
    const raw = c.replace(/[*_`]/g, '').trim();
    if (raw.includes(',') || raw.includes('"') || raw.includes('\n')) {
      return `"${raw.replace(/"/g, '""')}"`;
    }
    return raw;
  };

  const headerLine = headers.map(escapeCell).join(',');
  const rowLines = rows.map((r) => r.map(escapeCell).join(','));
  return [headerLine, ...rowLines].join('\n');
}

/**
 * Parses numeric variance or trend between two text cells.
 */
function parseVarianceBadge(text: string): {
  type: 'increase' | 'decrease' | 'neutral' | 'none';
  label: string;
} {
  const clean = text.replace(/[*_`]/g, '').trim();

  // Explicit delta markers
  if (clean.includes('+') || clean.includes('▲') || clean.toLowerCase().includes('increase')) {
    return { type: 'increase', label: clean };
  }
  if (clean.includes('-') || clean.includes('▼') || clean.toLowerCase().includes('decrease')) {
    return { type: 'decrease', label: clean };
  }
  if (clean.includes('—') || clean.toLowerCase().includes('unchanged') || clean.toLowerCase().includes('same')) {
    return { type: 'neutral', label: clean };
  }

  // Regex percentage match
  const pctMatch = clean.match(/([+-]?\d+(?:\.\d+)?%)/);
  if (pctMatch) {
    const val = parseFloat(pctMatch[1]);
    if (val > 0) return { type: 'increase', label: pctMatch[1] };
    if (val < 0) return { type: 'decrease', label: pctMatch[1] };
    return { type: 'neutral', label: pctMatch[1] };
  }

  return { type: 'none', label: clean };
}

export const ComparativeDiffGrid: React.FC<ComparativeDiffGridProps> = ({
  headers,
  alignments,
  rows,
  tableIdx,
  renderInline,
}) => {
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCopied, setIsCopied] = useState(false);
  const [copyFormat, setCopyFormat] = useState<'markdown' | 'csv'>('markdown');
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const gridContainerRef = useRef<HTMLDivElement>(null);
  const searchInputId = useId();

  // Filter rows by search term
  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return rows;
    const q = searchQuery.toLowerCase().trim();
    return rows.filter((row) => row.some((cell) => cell.toLowerCase().includes(q)));
  }, [rows, searchQuery]);

  const handleCopy = async (format: 'markdown' | 'csv') => {
    const text =
      format === 'markdown'
        ? formatTableAsMarkdown(headers, alignments, rows)
        : formatTableAsCsv(headers, rows);

    if (!text) return;
    const ok = await copyMarkdownToClipboard(text);
    if (ok) {
      setCopyFormat(format);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const toggleRowExpand = (idx: number) => {
    setExpandedRows((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Comparative target headers (Columns 1..N-1)
  const comparisonHeaders = headers.slice(1);

  return (
    <div className="relative my-5 rounded-2xl border border-slate-200/90 dark:border-white/10 bg-white/95 dark:bg-slate-900/90 shadow-md backdrop-blur-md overflow-hidden transition-all duration-200">
      {/* Top Interactive Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-4 py-3 bg-slate-50/90 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-white/10">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-500/10 dark:bg-indigo-400/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <Columns className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold tracking-wide uppercase text-slate-800 dark:text-slate-200">
                Comparative Diff Matrix
              </span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/60">
                {filteredRows.length} {filteredRows.length === 1 ? 'dimension' : 'dimensions'}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Side-by-side institutional report variance analysis
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Quick Filter */}
          <div className="relative flex items-center">
            <label htmlFor={searchInputId} className="sr-only">
              Filter comparative metrics
            </label>
            <Search className="w-3.5 h-3.5 absolute left-2.5 text-slate-400 pointer-events-none" />
            <input
              id={searchInputId}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter metrics..."
              aria-label="Filter metrics"
              className="pl-8 pr-2.5 py-1 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-hidden focus:ring-1.5 focus:ring-indigo-500/50 w-32 sm:w-44 transition-all"
            />
          </div>

          {/* View Toggle */}
          <div className="inline-flex items-center p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-900/80 text-xs">
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-2xs font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
              title="Side-by-side comparative diff grid view"
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Diff Grid</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
                viewMode === 'table'
                  ? 'bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-2xs font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
              title="Standard tabular view"
            >
              <TableIcon className="w-3.5 h-3.5" />
              <span>Table</span>
            </button>
          </div>

          {/* Copy Actions */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => handleCopy('markdown')}
              aria-label={isCopied && copyFormat === 'markdown' ? 'Copied Markdown' : 'Copy as Markdown'}
              title="Copy as Markdown"
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-all cursor-pointer shadow-2xs"
            >
              {isCopied && copyFormat === 'markdown' ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Copied!</span>
                </>
              ) : (
                <>
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  <span>MD</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => handleCopy('csv')}
              aria-label={isCopied && copyFormat === 'csv' ? 'Copied CSV' : 'Copy as CSV'}
              title="Copy as CSV"
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-all cursor-pointer shadow-2xs"
            >
              {isCopied && copyFormat === 'csv' ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Copied!</span>
                </>
              ) : (
                <>
                  <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
                  <span>CSV</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {viewMode === 'grid' ? (
        <div
          ref={gridContainerRef}
          className="max-h-[620px] overflow-y-auto divide-y divide-slate-100 dark:divide-white/5 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700"
        >
          {filteredRows.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              No comparative dimensions match &quot;{searchQuery}&quot;
            </div>
          ) : (
            filteredRows.map((row, rIdx) => {
              const dimensionText = row[0] || `Dimension ${rIdx + 1}`;
              const compCells = row.slice(1);
              const isExpanded = Boolean(expandedRows[rIdx]);

              return (
                <div
                  key={rIdx}
                  className="group/card p-4 hover:bg-slate-50/60 dark:hover:bg-white/[0.02] transition-colors"
                >
                  {/* Row Dimension Header */}
                  <div className="flex items-center justify-between gap-3 mb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center justify-center w-5 h-5 rounded-md text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                        {rIdx + 1}
                      </span>
                      <h4 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white tracking-tight">
                        {renderInline(dimensionText, `dim-${tableIdx}-${rIdx}`)}
                      </h4>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleRowExpand(rIdx)}
                      className="text-[11px] text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition-colors"
                      title={isExpanded ? 'Collapse row details' : 'Expand full details'}
                    >
                      {isExpanded ? 'Compact' : 'Detailed'}
                    </button>
                  </div>

                  {/* Side-by-Side Comparative Panes */}
                  <div
                    className={`grid gap-3 ${
                      compCells.length === 2
                        ? 'grid-cols-1 md:grid-cols-2'
                        : compCells.length === 3
                        ? 'grid-cols-1 md:grid-cols-3'
                        : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4'
                    }`}
                  >
                    {compCells.map((cellText, cIdx) => {
                      const colHeader = comparisonHeaders[cIdx] || `Document ${cIdx + 1}`;
                      const trimmed = cellText.trim();
                      const isStatus = isComparabilityStatus(trimmed);
                      const variance = parseVarianceBadge(trimmed);

                      return (
                        <div
                          key={cIdx}
                          className="flex flex-col justify-between p-3 rounded-xl border border-slate-200/80 dark:border-white/10 bg-white dark:bg-slate-900/60 shadow-2xs group-hover/card:border-slate-300 dark:group-hover/card:border-white/20 transition-all"
                        >
                          {/* Column Context Header */}
                          <div className="flex items-center justify-between gap-1.5 pb-1.5 mb-2 border-b border-slate-100 dark:border-white/5">
                            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 truncate max-w-[180px]">
                              {colHeader}
                            </span>

                            {/* Variance / Delta Pill */}
                            {variance.type === 'increase' && (
                              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                                <ArrowUpRight className="w-3 h-3 text-emerald-500" />
                                {variance.label}
                              </span>
                            )}
                            {variance.type === 'decrease' && (
                              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/30">
                                <ArrowDownRight className="w-3 h-3 text-rose-500" />
                                {variance.label}
                              </span>
                            )}
                            {variance.type === 'neutral' && (
                              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                                <Minus className="w-2.5 h-2.5" />
                                {variance.label}
                              </span>
                            )}
                          </div>

                          {/* Cell Evidence Body */}
                          <div
                            className={`text-xs text-slate-800 dark:text-slate-200 leading-relaxed ${
                              !isExpanded ? 'line-clamp-4' : ''
                            }`}
                          >
                            {isStatus ? (
                              <div className="py-1">
                                <ComparabilityBadge status={trimmed} />
                              </div>
                            ) : (
                              renderInline(cellText, `cell-${tableIdx}-${rIdx}-${cIdx}`)
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Standard Tabular View Fallback */
        <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700">
          <table className="w-full min-w-[640px] text-left text-xs sm:text-sm border-collapse">
            <thead className="sticky top-0 z-10 bg-slate-100/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200 dark:border-white/10 text-slate-800 dark:text-slate-200 font-semibold shadow-xs">
              <tr>
                {headers.map((h, hIdx) => (
                  <th
                    key={hIdx}
                    className={`px-4 py-2.5 font-semibold text-slate-900 dark:text-slate-100 whitespace-nowrap text-xs sm:text-sm tracking-tight ${
                      alignments[hIdx] || 'text-left'
                    }`}
                  >
                    {renderInline(h, `th-${tableIdx}-${hIdx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-white/5">
              {filteredRows.map((row, rIdx) => (
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
      )}
    </div>
  );
};
