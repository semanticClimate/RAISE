import { useCallback, useEffect, useState } from 'react';
import { chatService } from '../services/ChatService';

export interface UseSessionDrawerOptions {
  sessionId: string | null;
  initialDocs?: string[];
  onDrawerChange?: (docs: string[]) => void;
}

export interface UseSessionDrawerResult {
  attachedDocs: string[];
  isSyncing: boolean;
  attachDocument: (documentName: string) => Promise<void>;
  detachDocument: (documentName: string) => Promise<void>;
  toggleDocument: (documentName: string) => Promise<void>;
  setAttachedDocs: React.Dispatch<React.SetStateAction<string[]>>;
}

/**
 * useSessionDrawer:
 * Hook to manage active attached document state for the session drawer,
 * synchronizing with the backend REST endpoints and local thread cache.
 */
const getDrawerStorageKey = (id: string | null) =>
  id && id !== 'new' ? `raise_session_drawer_${id}` : 'raise_session_drawer_draft';

export function useSessionDrawer({
  sessionId,
  initialDocs = [],
  onDrawerChange,
}: UseSessionDrawerOptions): UseSessionDrawerResult {
  const storageKey = getDrawerStorageKey(sessionId);

  const [attachedDocs, setAttachedDocs] = useState<string[]>(() => {
    try {
      if (typeof window !== 'undefined') {
        const cached = localStorage.getItem(storageKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            return parsed.filter((d: unknown): d is string => typeof d === 'string');
          }
        }
      }
    } catch {}
    return initialDocs;
  });
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    if (initialDocs && initialDocs.length > 0) {
      setAttachedDocs(initialDocs);
    }
  }, [initialDocs]);

  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        localStorage.setItem(storageKey, JSON.stringify(attachedDocs));
      }
    } catch {}
  }, [storageKey, attachedDocs]);

  const attachDocument = useCallback(
    async (documentName: string) => {
      setAttachedDocs((prev) => {
        if (prev.includes(documentName)) return prev;
        const next = [...prev, documentName];
        onDrawerChange?.(next);
        return next;
      });

      if (sessionId && sessionId !== 'new') {
        setIsSyncing(true);
        try {
          await chatService.attachToSessionDrawer?.(sessionId, documentName);
        } catch (err) {
          console.warn(`Failed to attach document ${documentName} to session ${sessionId}:`, err);
        } finally {
          setIsSyncing(false);
        }
      }
    },
    [sessionId, onDrawerChange]
  );

  const detachDocument = useCallback(
    async (documentName: string) => {
      setAttachedDocs((prev) => {
        const next = prev.filter((d) => d !== documentName);
        onDrawerChange?.(next);
        return next;
      });

      if (sessionId && sessionId !== 'new') {
        setIsSyncing(true);
        try {
          await chatService.removeFromSessionDrawer?.(sessionId, documentName);
        } catch (err) {
          console.warn(`Failed to remove document ${documentName} from session ${sessionId}:`, err);
        } finally {
          setIsSyncing(false);
        }
      }
    },
    [sessionId, onDrawerChange]
  );

  const toggleDocument = useCallback(
    async (documentName: string) => {
      if (attachedDocs.includes(documentName)) {
        await detachDocument(documentName);
      } else {
        await attachDocument(documentName);
      }
    },
    [attachedDocs, attachDocument, detachDocument]
  );

  return {
    attachedDocs,
    isSyncing,
    attachDocument,
    detachDocument,
    toggleDocument,
    setAttachedDocs,
  };
}
