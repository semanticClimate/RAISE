/**
 * RAISE Unified Layout System
 * Single source of truth for responsive widths, container clamps, and vertical alignment lines.
 * Modifying values here guarantees synchronized updates across all corresponding views.
 */
export const RAISE_LAYOUT = {
  /**
   * Primary Search & Hero Column
   * Used by QueryBox container, RaiseHeroHeader, and empty-state stream containers.
   * Guarantees strict vertical edge alignment across all viewport sizes.
   */
  queryColumnWidth: 'max-w-[clamp(26rem,80vw,44rem)]',
  queryColumn: 'w-full max-w-[clamp(26rem,80vw,44rem)] mx-auto',
  queryHeader:
    'w-full max-w-[clamp(26rem,80vw,44rem)] mx-auto mb-4 sm:mb-6 text-left px-1 select-none space-y-3.5',

  /**
   * Full Research Conversation Stream
   * Expanded width for comfortable multi-column markdown tables, LaTeX, and reasoning traces.
   */
  streamContainer: 'w-full max-w-[min(100%,clamp(42rem,90vw,56rem))] mx-auto px-3 sm:px-4',

  /**
   * Dialog & Slide-over Width Presets
   */
  modalStandard: 'w-full max-w-2xl',
  modalWide: 'w-full max-w-4xl',
  modalFullPreview: 'w-full max-w-6xl',
} as const;
