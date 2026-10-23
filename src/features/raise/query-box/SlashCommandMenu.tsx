import {
  AlertTriangle,
  ArrowRight,
  Command,
  FileCheck2,
  FileSearch,
  HelpCircle,
  Network,
  Scale,
  Sparkles,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useRef } from 'react';
import type { SlashCommand } from '../../../schemas/commands';

export interface SlashCommandMenuProps {
  isOpen: boolean;
  commands: SlashCommand[];
  selectedIndex: number;
  onSelectCommand: (command: SlashCommand) => void;
  onHoverIndex: (index: number) => void;
  selectedDocCount: number;
  onOpenLibraryPicker?: () => void;
  onClose?: () => void;
  className?: string;
}

const getCategoryColor = (category: string) => {
  switch (category.toLowerCase()) {
    case 'comparison':
      return {
        bg: 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800/60',
        icon: <Scale className="w-3.5 h-3.5 text-indigo-500" />,
      };
    case 'verification':
      return {
        bg: 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/60',
        icon: <FileCheck2 className="w-3.5 h-3.5 text-emerald-500" />,
      };
    case 'synthesis':
      return {
        bg: 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800/60',
        icon: <Sparkles className="w-3.5 h-3.5 text-purple-500" />,
      };
    case 'knowledge graph':
      return {
        bg: 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/60',
        icon: <Network className="w-3.5 h-3.5 text-amber-500" />,
      };
    case 'diagnostics':
      return {
        bg: 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/60',
        icon: <FileSearch className="w-3.5 h-3.5 text-rose-500" />,
      };
    default:
      return {
        bg: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
        icon: <HelpCircle className="w-3.5 h-3.5 text-slate-500" />,
      };
  }
};

export const SlashCommandMenu: React.FC<SlashCommandMenuProps> = ({
  isOpen,
  commands,
  selectedIndex,
  onSelectCommand,
  onHoverIndex,
  selectedDocCount,
  onOpenLibraryPicker,
  onClose,
  className = '',
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Dismiss menu on click outside
  useEffect(() => {
    if (!isOpen) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose?.();
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen, onClose]);

  // Auto-scroll the selected item into view
  useEffect(() => {
    if (isOpen && itemRefs.current[selectedIndex]) {
      itemRefs.current[selectedIndex]?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth',
      });
    }
  }, [selectedIndex, isOpen]);

  if (!isOpen || commands.length === 0) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      role="listbox"
      aria-label="Slash commands autocomplete"
      className={`absolute bottom-full mb-2 left-0 sm:left-1 w-full sm:w-[480px] max-w-[calc(100vw-1.5rem)] bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2 duration-150 ${className}`}
    >
      {/* Header with Title and Keyboard Hints */}
      <div className="flex items-center justify-between px-3.5 py-2 border-b border-slate-100 dark:border-white/5 bg-slate-50/70 dark:bg-slate-800/40 select-none">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
          <Command className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
          <span>Slash Commands</span>
        </div>
        <div className="flex items-center gap-2 text-[10.5px] text-slate-600 dark:text-slate-400 font-mono">
          <span className="flex items-center gap-0.5">
            <kbd className="px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">↑</kbd>
            <kbd className="px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">↓</kbd>
            <span className="ml-0.5">navigate</span>
          </span>
          <span className="flex items-center gap-0.5">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">↵</kbd>
            <span className="ml-0.5">select</span>
          </span>
          <span className="flex items-center gap-0.5">
            <kbd className="px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">esc</kbd>
          </span>
        </div>
      </div>

      {/* Commands List */}
      <div className="max-h-[310px] overflow-y-auto p-1.5 space-y-1 divide-y divide-transparent">
        {commands.map((cmd, idx) => {
          const isSelected = selectedIndex === idx;
          const { bg, icon } = getCategoryColor(cmd.category);
          const isCompare = cmd.name === '/compare' || cmd.aliases?.includes('/diff');
          const lacksDocs = isCompare && selectedDocCount < 2;

          return (
            <div
              key={cmd.name}
              ref={(el) => {
                itemRefs.current[idx] = el;
              }}
              role="option"
              aria-selected={isSelected}
              tabIndex={-1}
              onClick={() => onSelectCommand(cmd)}
              onMouseEnter={() => onHoverIndex(idx)}
              className={`group flex flex-col p-2.5 rounded-xl cursor-pointer transition-all duration-150 select-none ${
                isSelected
                  ? 'bg-indigo-50/90 dark:bg-indigo-950/50 text-slate-900 dark:text-white ring-1 ring-indigo-500/30 dark:ring-indigo-400/30'
                  : 'hover:bg-slate-100/70 dark:hover:bg-white/[0.04] text-slate-700 dark:text-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="flex items-center justify-center w-6 h-6 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 group-hover:scale-105 transition-transform">
                    {icon}
                  </span>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-semibold font-mono text-sm text-indigo-600 dark:text-indigo-400">
                      {cmd.name}
                    </span>
                    <span className="text-[11.5px] font-mono text-slate-600 dark:text-slate-400 truncate max-w-[200px]">
                      {cmd.syntax.replace(cmd.name, '').trim()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium border ${bg}`}
                  >
                    {cmd.category}
                  </span>
                  {isSelected && (
                    <ArrowRight className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 animate-in fade-in slide-in-from-left-1 duration-100" />
                  )}
                </div>
              </div>

              {/* Description */}
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 leading-snug pl-8 line-clamp-2">
                {cmd.description}
              </p>

              {/* Guard Hint for /compare when fewer than 2 docs are attached */}
              {lacksDocs && (
                <div className="mt-1.5 ml-8 flex items-center justify-between text-[11px] px-2 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/50">
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    <span>Requires 2 attached documents (currently attached: {selectedDocCount})</span>
                  </div>
                  {onOpenLibraryPicker && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenLibraryPicker();
                      }}
                      className="ml-2 font-medium underline hover:text-amber-900 dark:hover:text-amber-200 shrink-0 cursor-pointer"
                    >
                      Attach
                    </button>
                  )}
                </div>
              )}

              {/* Aliases pill if available */}
              {cmd.aliases && cmd.aliases.length > 0 && !lacksDocs && (
                <div className="mt-1 ml-8 flex items-center gap-1 text-[10.5px] text-slate-500 dark:text-slate-400">
                  <span>Aliases:</span>
                  {cmd.aliases.map((alias) => (
                    <span
                      key={alias}
                      className="px-1 py-0.2 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[10px]"
                    >
                      {alias}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
