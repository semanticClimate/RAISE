import { useEffect } from 'react';

/**
 * Custom hook to lock body scrolling when a modal, dialog, or drawer is open.
 * Restores original overflow property on unmount or when unlocked.
 * Prevents dual scrollbars and background scroll chaining.
 */
export function useScrollLock(isLocked: boolean): void {
  useEffect(() => {
    if (!isLocked) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isLocked]);
}
