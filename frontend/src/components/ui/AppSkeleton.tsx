import type React from 'react';

/**
 * AppSkeleton Component
 * Pixel-accurate, zero-CLS (Cumulative Layout Shift) loading skeleton
 * mirroring the exact structural layout, fixed header, collapsed sidebar rail,
 * hero welcome title, and glass query box of the RAISE research application.
 */
export const AppSkeleton: React.FC = () => {
  return (
    <div
      role="status"
      aria-label="Loading RAISE application"
      className="bg-dot-pattern text-slate-900 dark:text-slate-100 h-screen h-dvh max-h-screen max-h-dvh antialiased flex flex-col font-sans select-none overflow-hidden relative"
    >
      {/* 1. Fixed Top Header matching MainHeader */}
      <header className="fixed top-0 left-0 sm:left-16 right-0 z-[55] bg-transparent border-b-0 px-3 sm:px-4 h-14 sm:h-16 flex items-center justify-between pointer-events-none select-none">
        {/* Brand Logo & Text */}
        <div className="flex items-center h-full">
          <div className="w-10 h-10 flex items-center justify-center shrink-0 sm:hidden mr-1">
            <div className="w-6 h-6 rounded-md bg-slate-200/80 dark:bg-white/[0.08] animate-pulse" />
          </div>
          <span className="text-[clamp(1.125rem,2.5vw,1.375rem)] font-bold tracking-tight text-slate-900 dark:text-white">
            RAISE
          </span>
        </div>

        {/* Right Action Trigger (Drawer button skeleton) */}
        <div className="flex items-center pr-1 sm:pr-0">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-slate-200/70 dark:bg-white/[0.06] border border-slate-300/60 dark:border-white/[0.08] animate-pulse" />
        </div>
      </header>

      {/* 2. Fixed Collapsed Sidebar Rail matching MainSidebar */}
      <aside className="hidden sm:flex fixed inset-y-0 left-0 w-16 z-30 bg-transparent border-r-0 flex-col pb-3.5 h-full space-y-3 select-none pointer-events-none">
        {/* Row 1: Expand Button Placeholder */}
        <div className="h-14 sm:h-16 flex items-center shrink-0 justify-center">
          <div className="w-10 h-10 rounded-xl bg-slate-200/60 dark:bg-white/[0.05] animate-pulse" />
        </div>

        {/* Row 2: New Chat Button Placeholder */}
        <div className="flex justify-center px-3">
          <div className="w-10 h-10 rounded-xl bg-slate-200/60 dark:bg-white/[0.05] animate-pulse" />
        </div>

        {/* Row 3: Search Button Placeholder */}
        <div className="flex justify-center px-3">
          <div className="w-10 h-10 rounded-xl bg-slate-200/60 dark:bg-white/[0.05] animate-pulse" />
        </div>

        {/* Bottom: Settings / Profile Placeholder */}
        <div className="mt-auto flex justify-center px-3">
          <div className="w-10 h-10 rounded-xl bg-slate-200/60 dark:bg-white/[0.05] animate-pulse" />
        </div>
      </aside>

      {/* 3. Main Workspace Container matching RaisePage */}
      <div className="flex-1 flex flex-col pl-0 sm:pl-16 w-full min-w-0 relative z-10 overflow-y-auto overflow-x-hidden mt-14 sm:mt-16">
        <main className="w-full max-w-2xl mx-auto px-[clamp(0.75rem,3vw,1.25rem)] flex-1 flex flex-col justify-center min-h-full py-4 sm:py-6 sm:-translate-y-6 transition-all duration-300">
          {/* Hero Welcome Header */}
          <section className="mb-4 sm:mb-6 text-center sm:text-left pt-2 sm:pt-0 select-none">
            <h1 className="text-[clamp(1.5rem,4.5vw,2.25rem)] font-semibold tracking-tight text-slate-900 dark:text-white mb-1.5 flex items-center justify-center sm:justify-start gap-2">
              <span>Welcome to RAISE</span>
            </h1>
            <p className="text-[clamp(0.8125rem,2.2vw,0.9375rem)] text-slate-500 dark:text-slate-400 font-normal leading-relaxed">
              Ask research questions, synthesize knowledge, or attach documents for deep analysis.
            </p>
          </section>

          {/* Interactive Query Box Skeleton */}
          <section className="w-full relative mb-1 sm:mb-0">
            <div className="glass-input-container rounded-[26px] sm:rounded-2xl flex flex-row items-center sm:flex-col sm:items-stretch sm:justify-between relative z-10 border border-slate-300/90 dark:border-white/[0.08] px-2 py-1 sm:p-3 gap-1 sm:gap-2 min-h-[44px] sm:min-h-[120px] bg-white/70 dark:bg-[#131622]/70 backdrop-blur-xl shadow-xs">
              {/* Query Input Placeholder */}
              <div className="order-2 sm:order-1 w-full flex-1 min-w-0 px-1 py-0.5 sm:pt-1 sm:pb-3 flex items-center">
                <div className="h-4 sm:h-5 w-48 rounded-md bg-slate-200/80 dark:bg-white/[0.07] animate-pulse" />
                <span className="hidden sm:inline-block w-[2px] h-[1.15em] bg-indigo-500/80 dark:bg-indigo-400/85 ml-1 animate-pulse align-middle rounded-full" />
              </div>

              {/* Bottom Query Controls Bar */}
              <div className="contents sm:flex sm:order-2 sm:w-full sm:items-center sm:justify-between sm:gap-2 relative z-20 sm:pt-1.5">
                {/* Left: + Add Source Button Skeleton */}
                <div className="order-1 sm:order-none flex items-center gap-2 shrink-0">
                  <div className="w-7.5 h-7.5 sm:w-8 sm:h-8 rounded-full bg-slate-200/80 dark:bg-white/[0.07] border border-slate-300/60 dark:border-white/[0.08] animate-pulse" />
                </div>

                {/* Right: Fast/Expert Toggle and Voice Mic Skeletons */}
                <div className="order-3 sm:order-none flex items-center justify-end space-x-1.5 sm:space-x-2 shrink-0 ml-auto">
                  <div className="w-20 h-7 sm:w-24 sm:h-8 rounded-full bg-slate-200/70 dark:bg-white/[0.06] border border-slate-300/60 dark:border-white/[0.08] animate-pulse" />
                  <div className="w-7.5 h-7.5 sm:w-8 sm:h-8 rounded-full bg-slate-200/70 dark:bg-white/[0.06] border border-slate-300/60 dark:border-white/[0.08] animate-pulse" />
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};
