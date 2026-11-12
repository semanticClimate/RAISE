import { isLegacySession } from '../../../utils/storageCleaner';
import type { ChatMessage, ChatSession } from '../types';
import { deduplicateTurns } from './messageNormalizer';

export const SESSIONS_STORAGE_KEY = 'raise_recent_sessions_v2';
export const CURRENT_SESSION_KEY = 'raise_current_session_id';
export const PERSIST_ON_RELOAD_KEY = 'raise_persist_session_on_reload';

let debounceSaveTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Prunes non-essential transient fields before writing to localStorage to prevent QuotaExceededError
 */
export function pruneSessionForStorage(session: ChatSession): ChatSession {
  return {
    ...session,
    messages: (session.messages || []).map((m) => {
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
          pipeline_info: cleanMsg.response.pipeline_info,
          storage_used: cleanMsg.response.storage_used,
          llm_model: cleanMsg.response.llm_model,
          llm_provider: cleanMsg.response.llm_provider,
          encoder_model: cleanMsg.response.encoder_model,
          reranker_model: cleanMsg.response.reranker_model,
          nli_verifier_model: cleanMsg.response.nli_verifier_model,
        };
      }
      return cleanMsg;
    }),
  };
}

export function loadSessionsLocally(): ChatSession[] {
  try {
    if (typeof window === 'undefined') return [];
    const cached = localStorage.getItem(SESSIONS_STORAGE_KEY);
    if (cached) {
      const parsed = JSON.parse(cached) as ChatSession[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
          .filter((s) => !isLegacySession(s))
          .map((s) => {
            const rawTime = s.updated_at || s.created_at;
            const validIso =
              rawTime && !Number.isNaN(new Date(rawTime).getTime())
                ? new Date(rawTime).toISOString()
                : s.timestamp && !Number.isNaN(new Date(s.timestamp).getTime())
                  ? new Date(s.timestamp).toISOString()
                  : new Date().toISOString();
            return {
              ...s,
              timestamp: validIso,
              updated_at: s.updated_at || validIso,
              created_at: s.created_at || validIso,
            };
          });
      }
    }
    return [];
  } catch {
    return [];
  }
}

export function saveSessionsLocally(newSessions: ChatSession[], immediate: boolean = false): void {
  const performSave = () => {
    try {
      if (typeof window === 'undefined') return;
      const pruned = newSessions.map(pruneSessionForStorage);
      localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(pruned));
    } catch (err: unknown) {
      // Handle QuotaExceededError by keeping only recent 15 sessions
      if (err instanceof Error && err.name === 'QuotaExceededError') {
        try {
          const minimal = newSessions.slice(0, 15).map(pruneSessionForStorage);
          localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(minimal));
        } catch {
          // fallback ignore
        }
      }
    }
  };

  if (immediate) {
    if (debounceSaveTimer) clearTimeout(debounceSaveTimer);
    performSave();
    return;
  }

  if (debounceSaveTimer) clearTimeout(debounceSaveTimer);
  debounceSaveTimer = setTimeout(performSave, 350);
}

export function getInitialSessionId(): string | null {
  try {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(CURRENT_SESSION_KEY)?.trim();
      if (stored) {
        return stored;
      }
      const cached = localStorage.getItem(SESSIONS_STORAGE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached) as ChatSession[];
        if (parsed.length > 0) return parsed[0].id;
      }
    }
  } catch {}
  return null;
}

export function getInitialConversation(): ChatMessage[] {
  try {
    if (typeof window !== 'undefined') {
      const targetId = localStorage.getItem(CURRENT_SESSION_KEY)?.trim();
      const cached = localStorage.getItem(SESSIONS_STORAGE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached) as ChatSession[];
        const match = (targetId ? parsed.find((s) => s.id === targetId) : null) || parsed[0];
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
  } catch {}
  return [];
}
