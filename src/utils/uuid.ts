/**
 * Cross-Session UUID and Chat Session Date Utilities
 */

/**
 * Generates an RFC4122 v4 compliant UUID.
 * Uses native crypto.randomUUID() when available, with a robust fallback.
 */
export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID();
    } catch {
      // fallback if crypto.randomUUID fails in restricted iframe/context
    }
  }

  // RFC4122 v4 UUID generator
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Truncates user query to create a readable chat session title.
 */
export function truncateSessionTitle(text: string, maxLength: number = 42): string {
  const cleaned = text.trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'New Chat';
  if (cleaned.length <= maxLength) return cleaned;
  return `${cleaned.slice(0, maxLength).trim()}...`;
}

/**
 * Formats a session timestamp or date string into human-friendly representation for the sidebar.
 * e.g. "Just now", "5m ago", "Today, 11:45 AM", "Yesterday, 4:20 PM", "Nov 12", "Nov 12, 2025".
 */
export function formatSessionDate(
  dateVal?: string | number | Date,
  fallbackDate?: string | number | Date
): string {
  let target = dateVal;
  if ((!target || target === 'Just now' || target === 'Recent') && fallbackDate) {
    target = fallbackDate;
  }

  if (!target || target === 'Recent') return 'Recent';

  // If already a relative formatted string with ago or Today
  if (
    typeof target === 'string' &&
    (target.includes('ago') || target.startsWith('Today,'))
  ) {
    return target;
  }

  const d = new Date(target);
  if (Number.isNaN(d.getTime())) {
    if (fallbackDate && fallbackDate !== target) {
      const fb = new Date(fallbackDate);
      if (!Number.isNaN(fb.getTime())) {
        return formatCalculatedDate(fb);
      }
    }
    return typeof target === 'string' ? target : 'Recent';
  }

  return formatCalculatedDate(d);
}

function formatCalculatedDate(d: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();

  // If created within the last 60 seconds
  if (diffMs >= 0 && diffMs < 60 * 1000) {
    return 'Just now';
  }

  // If created within the last 60 minutes
  if (diffMs >= 60 * 1000 && diffMs < 60 * 60 * 1000) {
    const mins = Math.max(1, Math.floor(diffMs / (60 * 1000)));
    return `${mins}m ago`;
  }

  // Same day
  if (
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear()
  ) {
    return `Today, ${d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  }

  // Yesterday
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (
    d.getDate() === yesterday.getDate() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getFullYear() === yesterday.getFullYear()
  ) {
    return `Yesterday, ${d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  }

  // Within current year: "Nov 12"
  if (d.getFullYear() === now.getFullYear()) {
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  // Older years: "Nov 12, 2025"
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}
