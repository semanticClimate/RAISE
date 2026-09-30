import type { RefObject } from 'react';
import { useClickOutside } from './useClickOutside';
import { useEscapeKey } from './useEscapeKey';

/**
 * Composite hook for dismissable overlays (popovers, dropdowns, contextual menus).
 * Triggers onDismiss when clicking outside or pressing the Escape key.
 */
export function useDismissable<T extends HTMLElement = HTMLElement>(
  ref: RefObject<T | null>,
  isOpen: boolean,
  onDismiss: () => void
): void {
  useClickOutside(ref, onDismiss, isOpen);
  useEscapeKey(onDismiss, isOpen);
}
