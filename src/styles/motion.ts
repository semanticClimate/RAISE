/**
 * RAISE Motion System Tokens
 * Governed by motion-design-skill and modern-web-guidance principles.
 * Archetype: Corporate (clean, professional, responsive, dashboard).
 */

export const RAISE_MOTION = {
  /**
   * Standard Cubic-Bezier Easing Curves
   */
  easing: {
    // Standard on-screen transitions (Material 3 / Snappy UI)
    standard: 'cubic-bezier(0.2, 0, 0, 1)',
    // Entrances: fast start, gentle decelerating landing
    enter: 'cubic-bezier(0, 0, 0.2, 1)',
    // Exits: gentle start, fast accelerating departure
    exit: 'cubic-bezier(0.4, 0, 1, 1)',
    // Ambient / subtle background breathing
    ambient: 'cubic-bezier(0.4, 0, 0.2, 1)',
    // Micro feedback: instant spring-like settling
    spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.1)',
  },

  /**
   * Duration Budget Tokens (in milliseconds and CSS strings)
   */
  duration: {
    // Micro feedback, tooltips, icon state toggles
    micro: '100ms',
    // Button clicks, badge changes, toggles
    fast: '150ms',
    // Cards entering, accordion expands, tab switches
    normal: '250ms',
    // Dialog / modal focus shifts, drawer slide-overs
    deliberate: '350ms',
    // Major context switches or multi-element reveals
    complex: '500ms',
  },

  /**
   * Choreography Stagger Budgets
   */
  stagger: {
    item: 30, // 30ms between successive items
    max: 300, // Maximum cumulative stagger budget (never exceed 500ms)
  },
} as const;

/**
 * Common pre-composed Tailwind / CSS transition utility classes
 */
export const MOTION_CLASSES = {
  transitionFast: 'transition-all duration-150 ease-[cubic-bezier(0.2,0,0,1)]',
  transitionNormal: 'transition-all duration-250 ease-[cubic-bezier(0.2,0,0,1)]',
  transitionDeliberate: 'transition-all duration-350 ease-[cubic-bezier(0.2,0,0,1)]',
  modalEnter: 'transition duration-350 ease-[cubic-bezier(0,0,0.2,1)]',
  modalExit: 'transition duration-200 ease-[cubic-bezier(0.4,0,1,1)]',
} as const;
