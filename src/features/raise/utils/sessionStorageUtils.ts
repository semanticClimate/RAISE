import { isLegacySession } from '../../../utils/storageCleaner';
import { DEMO_SHOWCASE_SESSION, DEMO_SHOWCASE_SESSION_ID } from '../showcaseSession';
import type { ChatMessage, ChatSession } from '../types';
import { deduplicateTurns } from './messageNormalizer';

export const SESSIONS_STORAGE_KEY = 'raise_recent_sessions_v2';
export const CURRENT_SESSION_KEY = 'raise_current_session_id';
export const DEMO_DELETED_KEY = 'raise_demo_showcase_deleted';
export const PERSIST_ON_RELOAD_KEY = 'raise_persist_session_on_reload';

let debounceSaveTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Prunes non-essential transient fields before writing to localStorage to prevent QuotaExceededError
 */
export function pruneSessionForStorage(session: ChatSession): ChatSession {
  return {
    ...session,
    messages: (session.messages || []).map((m) => {
      // Retain essential display fields, citations, and versions; strip huge debug payloads
      const { ...cleanMsg } = m;
      if (cleanMsg.response) {
        cleanMsg.response = {
          grounded_answer: cleanMsg.response.grounded_answer,
          answer: cleanMsg.response.answer,
          citations: cleanMsg.response.citations,
          verified_claims: cleanMsg.response.verified_claims,
          confidence_score: cleanMsg.response.confidence_score,
          quality_gate_decision: cleanMsg.response.quality_gate_decision,
          duration_seconds: cleanMsg.response.duration_seconds,
        };
      }
      return cleanMsg;
    }),
  };
}

export function loadSessionsLocally(): ChatSession[] {
  try {
    if (typeof window === 'undefined') return [DEMO_SHOWCASE_SESSION];
    const cached = localStorage.getItem(SESSIONS_STORAGE_KEY);
    const isDemoDeleted = localStorage.getItem(DEMO_DELETED_KEY) === 'true';

    if (cached) {
      const parsed = JSON.parse(cached) as ChatSession[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        const cleaned = parsed.filter((s) => !isLegacySession(s));
        const hasDemo = cleaned.some((s) => s.id === DEMO_SHOWCASE_SESSION_ID);
        const withDemo = hasDemo || isDemoDeleted ? cleaned : [...cleaned, DEMO_SHOWCASE_SESSION];
        return withDemo;
      }
    }
    return isDemoDeleted ? [] : [DEMO_SHOWCASE_SESSION];
  } catch {
    return [DEMO_SHOWCASE_SESSION];
  }
}

export function saveSessionsLocally(newSessions: ChatSession[], immediate: boolean = false): void {
  const performSave = () => {
    try {
      if (typeof window === 'undefined') return;
      const pruned = newSessions.map(pruneSessionForStorage);
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(pruned));
    } catch (e) {
      console.warn('Failed to cache chat sessions locally:', e);
    }
  };

  if (immediate) {
    if (debounceSaveTimer) clearTimeout(debounceSaveTimer);
    performSave();
    return;
  }

  if (debounceSaveTimer) {
    clearTimeout(debounceSaveTimer);
  }
  debounceSaveTimer = setTimeout(performSave, 350);
}

export function getInitialSessionId(): string | null {
  try {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const urlSession = urlParams.get('session') || urlParams.get('session_id');
      if (urlSession && urlSession.trim()) {
        return urlSession.trim();
      }
    }
    const shouldPersist = localStorage.getItem(PERSIST_ON_RELOAD_KEY) === 'true';
    if (!shouldPersist) return null;

    const savedCurrentId = localStorage.getItem(CURRENT_SESSION_KEY);
    if (savedCurrentId && savedCurrentId.trim()) {
      return savedCurrentId.trim();
    }
  } catch {}
  return null;
}

export function getInitialConversation(): ChatMessage[] {
  try {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const urlSession = urlParams.get('session') || urlParams.get('session_id');
      const shouldPersist = localStorage.getItem(PERSIST_ON_RELOAD_KEY) === 'true';
      const targetId =
        urlSession?.trim() ||
        (shouldPersist ? localStorage.getItem(CURRENT_SESSION_KEY)?.trim() : null);

      if (targetId) {
        const cached = localStorage.getItem(SESSIONS_STORAGE_KEY);
        if (cached) {
          const parsed = JSON.parse(cached) as ChatSession[];
          const match = parsed.find((s) => s.id === targetId);
          if (match && Array.isArray(match.messages) && match.messages.length > 0) {
            return deduplicateTurns(
              match.messages.map((m: any) => ({
                ...m,
                text: m?.text || m?.content || '',
                content: m?.content || m?.text || '',
              }))
            );
          }
        }
      }
    }
  } catch {}
  return [];
}
