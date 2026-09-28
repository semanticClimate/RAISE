/**
 * Legacy Mock Session Cleanser
 *
 * Automatically detects and purges deprecated hardcoded mock chat sessions
 * (e.g., XYMA, Mindgrove, NeoMotion, IITMRP) from browser storage.
 */

export function isLegacyMockSession(
  session: { id?: string; title?: string } | null | undefined
): boolean {
  if (!session) return false;
  const id = (session.id || '').toLowerCase();
  const title = (session.title || '').toLowerCase();

  return (
    id.startsWith('session-xyma') ||
    id.startsWith('session-iitmrp') ||
    id.startsWith('session-ultrasonic') ||
    id.startsWith('session-neomotion') ||
    id === 'session-1' ||
    id === 'session-2' ||
    title.includes('xyma') ||
    title.includes('neomotion') ||
    title.includes('mindgrove') ||
    title.includes('iit madras research park') ||
    title.includes('ultrasonic waveguide')
  );
}

export function cleanseLegacyMockStorage(): void {
  if (typeof window === 'undefined' || !window.localStorage) return;

  try {
    // 1. Cleanse raise_recent_sessions_v2
    const recentRaw = localStorage.getItem('raise_recent_sessions_v2');
    if (recentRaw) {
      const parsed = JSON.parse(recentRaw) as unknown[];
      if (Array.isArray(parsed)) {
        const cleaned = parsed.filter(
          (s) => !isLegacyMockSession(s as { id?: string; title?: string })
        );
        if (cleaned.length !== parsed.length) {
          localStorage.setItem('raise_recent_sessions_v2', JSON.stringify(cleaned));
        }
      }
    }

    // 2. Cleanse legacy raise_chat_sessions
    const oldSessionsRaw = localStorage.getItem('raise_chat_sessions');
    if (oldSessionsRaw) {
      const parsed = JSON.parse(oldSessionsRaw) as unknown[];
      if (Array.isArray(parsed)) {
        const cleaned = parsed.filter(
          (s) => !isLegacyMockSession(s as { id?: string; title?: string })
        );
        if (cleaned.length !== parsed.length) {
          localStorage.setItem('raise_chat_sessions', JSON.stringify(cleaned));
        }
      }
    }

    // 3. Cleanse raise_archived_sessions
    const archivedRaw = localStorage.getItem('raise_archived_sessions');
    if (archivedRaw) {
      const parsed = JSON.parse(archivedRaw) as unknown[];
      if (Array.isArray(parsed)) {
        const cleaned = parsed.filter(
          (s) => !isLegacyMockSession(s as { id?: string; title?: string })
        );
        if (cleaned.length !== parsed.length) {
          localStorage.setItem('raise_archived_sessions', JSON.stringify(cleaned));
        }
      }
    }

    // 4. Cleanse raise_pinned_sessions
    const pinnedRaw = localStorage.getItem('raise_pinned_sessions');
    if (pinnedRaw) {
      const parsed = JSON.parse(pinnedRaw) as unknown[];
      if (Array.isArray(parsed)) {
        const cleaned = parsed.filter(
          (id) =>
            typeof id === 'string' &&
            !id.startsWith('session-xyma') &&
            !id.startsWith('session-iitmrp') &&
            !id.startsWith('session-ultrasonic') &&
            !id.startsWith('session-neomotion')
        );
        if (cleaned.length !== parsed.length) {
          localStorage.setItem('raise_pinned_sessions', JSON.stringify(cleaned));
        }
      }
    }

    // 5. Cleanse active conversation if it matches mock
    const activeConvoRaw = localStorage.getItem('raise_active_conversation');
    if (activeConvoRaw) {
      const parsed = JSON.parse(activeConvoRaw) as unknown[];
      if (Array.isArray(parsed)) {
        const hasMockContent = parsed.some(
          (m: any) =>
            typeof m?.text === 'string' &&
            (m.text.toLowerCase().includes('xyma') ||
              m.text.toLowerCase().includes('neomotion') ||
              m.text.toLowerCase().includes('mindgrove'))
        );
        if (hasMockContent) {
          localStorage.removeItem('raise_active_conversation');
        }
      }
    }
  } catch {
    // Graceful fallback if JSON parsing fails
  }
}
