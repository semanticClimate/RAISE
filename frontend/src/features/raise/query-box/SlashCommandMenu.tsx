import {
  GitCompare,
  Globe,
  HelpCircle,
  ShieldCheck,
  Terminal,
  Zap,
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

// Map dedicated clean SVGs for each slash command
export const getCommandIcon = (cmdName: string) => {
  const name = cmdName.toLowerCase();
  if (name.includes('boost') || name.includes('turbo') || name.includes('accelerate') || name.includes('perf')) {
    return <Zap className="w-3.5 h-3.5 text-amber-400" />;
  }
  if (name.includes('compare') || name.includes('diff') || name.includes('vs')) {
    return <GitCompare className="w-3.5 h-3.5 text-indigo-400" />;
  }
  if (name.includes('browser') || name.includes('web') || name.includes('fetch')) {
    return <Globe className="w-3.5 h-3.5 text-cyan-400" />;
  }
  if (name.includes('audit') || name.includes('verify') || name.includes('factcheck')) {
    return <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />;
  }
  if (name.includes('help')) {
    return <HelpCircle className="w-3.5 h-3.5 text-amber-400" />;
  }
  return <Terminal className="w-3.5 h-3.5 text-slate-400" />;
};

// Sid says: Sleek dark floating box command palette without clutter, headers, or keyboard legends
export const SlashCommandMenu: React.FC<SlashCommandMenuProps> = ({
  isOpen,
  commands,
  selectedIndex,
  onSelectCommand,
  onHoverIndex,
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
      aria-label="Commands autocomplete"
      className={`absolute bottom-full mb-2 left-0 sm:left-1 w-full sm:w-[420px] max-w-[calc(100vw-1.5rem)] bg-[#12131a] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 p-1.5 animate-in fade-in slide-in-from-bottom-2 duration-150 backdrop-blur-xl ${className}`}
    >
      <div className="max-h-[260px] overflow-y-auto space-y-0.5 no-scrollbar">
        {commands.map((cmd, idx) => {
          const isSelected = selectedIndex === idx;

          return (
            <div
              key={cmd.name}
              ref={(el) => {
                itemRefs.current[idx] = el;
              }}
              role="option"
              aria-selected={isSelected}
              tabIndex={-1}
              onMouseDown={(e) => {
                // Sid says: Prevent textarea blur before command selection registers
                e.preventDefault();
              }}
              onClick={() => onSelectCommand(cmd)}
              onMouseEnter={() => onHoverIndex(idx)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-colors duration-100 select-none ${
                isSelected
                  ? 'bg-white/10 text-white'
                  : 'hover:bg-white/5 text-slate-300'
              }`}
            >
              <div className="flex items-center justify-center w-6 h-6 rounded-md bg-white/[0.06] shrink-0">
                {getCommandIcon(cmd.name)}
              </div>
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <span className="font-semibold text-[13px] text-white font-mono shrink-0">
                  {cmd.name}
                </span>
                <span className="text-xs text-slate-400 truncate">
                  {cmd.description}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
