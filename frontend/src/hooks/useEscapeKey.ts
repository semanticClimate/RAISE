import { useEffect } from 'react';

/**
 * Custom hook to detect when the user presses the Escape key.
 * Encapsulates keyboard listeners and active state management.
 */
export function useEscapeKey(handler: () => void, active = true): void {
  useEffect(() => {
    if (!active) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handler();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handler, active]);
}
