import { FileUp, FolderPlus } from 'lucide-react';
import type React from 'react';

export interface EmptyWorkspaceNoticeCardProps {
  onOpenDrawer: () => void;
  className?: string;
}

// Sleek, compact 1-line prompt to attach an academic document
export const EmptyWorkspaceNoticeCard: React.FC<EmptyWorkspaceNoticeCardProps> = ({
  onOpenDrawer,
  className = '',
}) => {
  return (
    <div
      className={`empty-workspace-notice-card mt-2.5 p-2 px-3 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200/60 dark:border-indigo-800/40 flex items-center justify-between gap-2.5 animate-in fade-in duration-150 ${className}`}
      data-testid="empty-workspace-notice-card"
    >
      <div className="flex items-center gap-2 min-w-0">
        <FolderPlus className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 shrink-0" />
        <span className="text-xs text-slate-700 dark:text-slate-300 truncate">
          Attach a document to start research analysis.
        </span>
      </div>

      <button
        type="button"
        onClick={onOpenDrawer}
        data-testid="attach-document-from-notice-btn"
        className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-2xs active:scale-95 transition-all flex items-center gap-1 cursor-pointer shrink-0"
      >
        <FileUp className="w-3 h-3" />
        <span>Attach</span>
      </button>
    </div>
  );
};
