import { Check, Download, FileCode, FileText, Printer } from 'lucide-react';
import type React from 'react';
import { useRef, useState } from 'react';
import { useDismissable } from '../../hooks';
import type { SubgraphQueryResponse } from '../../types';
import {
  exportAsJson,
  exportAsMarkdown,
  exportAsPdf,
  printReportWindow,
} from '../../utils/exportFormats';

export interface ExportResponseDropdownProps {
  query: string;
  answerText: string;
  response?: Partial<SubgraphQueryResponse>;
  onExport?: (format: 'md' | 'pdf' | 'json' | 'print') => void;
  align?: 'left' | 'right';
  className?: string;
}

export const ExportResponseDropdown: React.FC<ExportResponseDropdownProps> = ({
  query,
  answerText,
  response,
  onExport,
  align = 'left',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [exportedFormat, setExportedFormat] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside or escape key via custom hook
  useDismissable(containerRef, isOpen, () => setIsOpen(false));

  const handleExport = (format: 'md' | 'pdf' | 'json' | 'print') => {
    try {
      if (format === 'md') {
        exportAsMarkdown(query, answerText, response);
      } else if (format === 'pdf') {
        exportAsPdf(query, answerText, response);
      } else if (format === 'print') {
        printReportWindow(query, answerText, response);
      } else if (format === 'json') {
        exportAsJson(query, answerText, response);
      }

      setExportedFormat(format);
      onExport?.(format);

      setTimeout(() => {
        setExportedFormat((cur) => (cur === format ? null : cur));
      }, 2500);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className={`relative inline-flex items-center ${className}`}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="Export response"
        aria-haspopup="true"
        aria-expanded={isOpen}
        title={exportedFormat ? `Exported ${exportedFormat.toUpperCase()}!` : 'Export response'}
        className={`p-1.5 rounded-lg active:scale-95 transition-all cursor-pointer flex items-center justify-center ${
          isOpen
            ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/20 ring-1 ring-indigo-500/40'
            : exportedFormat
              ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/15'
              : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/5'
        }`}
      >
        {exportedFormat ? (
          <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 animate-in zoom-in duration-150" />
        ) : (
          <Download className="w-3.5 h-3.5" />
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="menu"
          aria-orientation="vertical"
          data-testid="export-dropdown-menu"
          className={`absolute bottom-full mb-2 ${
            align === 'right' ? 'right-0' : 'left-0'
          } w-68 p-1.5 bg-white dark:bg-[#151928] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150 text-left`}
        >
          {/* Header */}
          <div className="px-2.5 py-1.5 border-b border-slate-100 dark:border-white/5 mb-1 flex items-center justify-between">
            <span className="text-[10px] font-bold tracking-wider uppercase text-slate-400 dark:text-slate-500">
              Export Research Response
            </span>
            <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">
              A4 Justified
            </span>
          </div>

          {/* Option 1: Markdown (.md) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('md')}
            className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-start gap-2.5 group"
          >
            <div className="p-1.5 rounded-md bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 group-hover:bg-slate-200/70 dark:group-hover:bg-white/10 group-hover:text-slate-800 dark:group-hover:text-slate-200 transition-colors shrink-0 mt-0.5">
              <FileText className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Markdown (.md)</span>
                <span className="text-[10px] text-slate-400 font-mono">Report</span>
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-400/90 leading-snug">
                Formatted markdown with source citations
              </p>
            </div>
          </button>

          {/* Option 2: PDF Document (.pdf) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('pdf')}
            className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-start gap-2.5 group"
          >
            <div className="p-1.5 rounded-md bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 group-hover:bg-slate-200/70 dark:group-hover:bg-white/10 group-hover:text-slate-800 dark:group-hover:text-slate-200 transition-colors shrink-0 mt-0.5">
              <Download className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">PDF Report (.pdf)</span>
                <span className="text-[10px] text-slate-400 font-mono">ISO A4</span>
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-400/90 leading-snug">
                A4 justified document with metadata &amp; citations
              </p>
            </div>
          </button>

          {/* Option 3: Print / Save as PDF (A4) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('print')}
            className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-start gap-2.5 group"
          >
            <div className="p-1.5 rounded-md bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 group-hover:bg-slate-200/70 dark:group-hover:bg-white/10 group-hover:text-slate-800 dark:group-hover:text-slate-200 transition-colors shrink-0 mt-0.5">
              <Printer className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Print / Save PDF</span>
                <span className="text-[10px] text-slate-400 font-mono">Print</span>
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-400/90 leading-snug">
                Browser print preview (ISO A4 Justified)
              </p>
            </div>
          </button>

          {/* Option 4: Developer JSON (.json) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('json')}
            className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-white/5 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-start gap-2.5 group"
          >
            <div className="p-1.5 rounded-md bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400 group-hover:bg-slate-200/70 dark:group-hover:bg-white/10 group-hover:text-slate-800 dark:group-hover:text-slate-200 transition-colors shrink-0 mt-0.5">
              <FileCode className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Structured JSON (.json)</span>
                <span className="text-[10px] text-slate-400 font-mono">Raw</span>
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-400/90 leading-snug">
                Complete response and citation metadata
              </p>
            </div>
          </button>
        </div>
      )}
    </div>
  );
};
