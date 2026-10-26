import { FileUp, FolderPlus } from 'lucide-react';
import type React from 'react';

export interface EmptyWorkspaceNoticeCardProps {
  onOpenDrawer: () => void;
  className?: string;
}

// Sid says: Prominent 1-click Attach Document button displayed inside or below empty drawer responses
export const EmptyWorkspaceNoticeCard: React.FC<EmptyWorkspaceNoticeCardProps> = ({
  onOpenDrawer,
  className = '',
}) => {
  return (
    <div
      className={`empty-workspace-notice-card mt-3 p-3.5 sm:p-4 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-800/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in slide-in-from-bottom-1 duration-200 shadow-2xs ${className}`}
      data-testid="empty-workspace-notice-card"
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <div className="w-8 h-8 rounded-xl bg-indigo-600/10 dark:bg-indigo-400/15 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
          <FolderPlus className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h4 className="text-xs font-bold text-slate-900 dark:text-white">
            Workspace Document Required
          </h4>
          <p className="text-[11.5px] text-slate-600 dark:text-slate-300 mt-0.5 leading-snug">
            Attach an academic PDF or report from your PC or knowledge library to start research analysis.
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={onOpenDrawer}
        data-testid="attach-document-from-notice-btn"
        className="w-full sm:w-auto px-4 py-2 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs active:scale-95 transition-all flex items-center justify-center gap-1.5 cursor-pointer shrink-0"
      >
        <FileUp className="w-3.5 h-3.5" />
        <span>Attach Document</span>
      </button>
    </div>
  );
};
