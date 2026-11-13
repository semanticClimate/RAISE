import { Check, Download, FileCode, FileText, Printer } from 'lucide-react';
import type React from 'react';
import { useEffect, useRef, useState } from 'react';
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

  useEffect(() => {
    if (!exportedFormat) return;
    const timer = setTimeout(() => {
      setExportedFormat(null);
    }, 2500);
    return () => clearTimeout(timer);
  }, [exportedFormat]);

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
          } w-48 p-1 bg-white dark:bg-[#151928] border border-slate-200 dark:border-white/10 rounded-xl shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150 text-left`}
        >
          {/* Option 1: Markdown (.md) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('md')}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-center gap-2 group text-xs font-medium whitespace-nowrap"
          >
            <FileText className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200 shrink-0" />
            <span>Markdown (.md)</span>
          </button>

          {/* Option 2: PDF Document (.pdf) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('pdf')}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-center gap-2 group text-xs font-medium whitespace-nowrap"
          >
            <Download className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200 shrink-0" />
            <span>PDF Document (.pdf)</span>
          </button>

          {/* Option 3: Print Report */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('print')}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-center gap-2 group text-xs font-medium whitespace-nowrap"
          >
            <Printer className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200 shrink-0" />
            <span>Print Report</span>
          </button>

          {/* Option 4: Developer JSON (.json) */}
          <button
            type="button"
            role="menuitem"
            onClick={() => handleExport('json')}
            className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer flex items-center gap-2 group text-xs font-medium whitespace-nowrap"
          >
            <FileCode className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200 shrink-0" />
            <span>JSON Data (.json)</span>
          </button>
        </div>
      )}
    </div>
  );
};
