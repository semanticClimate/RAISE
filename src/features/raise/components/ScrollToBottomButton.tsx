import type React from 'react';

export interface ScrollToBottomButtonProps {
  show: boolean;
  onScrollToBottom: () => void;
}

/**
 * Floating Scroll to Bottom Down Arrow Button (ChatGPT / Gemini style).
 * Rendered when user has scrolled up while reading conversation stream.
 */
export const ScrollToBottomButton: React.FC<ScrollToBottomButtonProps> = ({
  show,
  onScrollToBottom,
}) => {
  if (!show) return null;

  return (
    <div className="fixed bottom-24 sm:bottom-28 left-1/2 -translate-x-1/2 z-40 flex justify-center pointer-events-none">
      <button
        type="button"
        data-testid="scroll-to-bottom-btn"
        aria-label="Scroll to bottom"
        onClick={onScrollToBottom}
        className="pointer-events-auto flex items-center justify-center w-8 h-8 rounded-full bg-[#171717] hover:bg-[#292929] border border-[#292929] text-[#FFFFFF] shadow-xl transition-all active:scale-95 cursor-pointer animate-in fade-in slide-in-from-bottom-2 duration-150"
      >
        <svg
          className="w-4 h-4 text-[#FFFFFF]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
    </div>
  );
};
