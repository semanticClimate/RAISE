import type React from 'react';

/**
 * AppSkeleton Component
 * Clean, subtle, and unobtrusive loading indicator.
 * Eliminates heavy skeleton screens, pulsating shadow boxes, and layout jarring.
 */
export const AppSkeleton: React.FC = () => {
  return (
    <div
      role="status"
      aria-label="Loading RAISE application"
      className="fixed inset-0 z-50 flex items-center justify-center bg-transparent pointer-events-none select-none"
    >
      <div className="w-6 h-6 rounded-full border-2 border-slate-300 dark:border-white/10 border-t-indigo-500 animate-spin" />
    </div>
  );
};
