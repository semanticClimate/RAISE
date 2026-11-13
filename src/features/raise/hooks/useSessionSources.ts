import { useCallback, useEffect, useState } from 'react';
import type { LibraryItem } from '../../../components/settings/SettingsLibraryTab';
import { chatService } from '../../../services/ChatService';
import { sourceService } from '../../../services/SourceService';
import { formatBytes } from '../../../utils/formatters';
import type { ChatSession, SourceDocument } from '../types';
import { DRAFT_SOURCES_STORAGE_KEY, getInitialSourceDocs } from '../utils/sessionStorageUtils';

export interface UseSessionSourcesOptions {
  currentSessionId?: string | null;
  activeSessionIdRef?: React.RefObject<string | null>;
  setSessions: React.Dispatch<React.SetStateAction<ChatSession[]>>;
}

export function useSessionSources({
  currentSessionId,
  activeSessionIdRef,
  setSessions,
}: UseSessionSourcesOptions) {
  const [sourceDocs, setSourceDocs] = useState<SourceDocument[]>(getInitialSourceDocs);
  const [isSourcesDrawerOpen, setIsSourcesDrawerOpen] = useState(false);
  const [isLibraryPickerOpen, setIsLibraryPickerOpen] = useState(false);
  const [apiReadyFilenames, setApiReadyFilenames] = useState<Set<string>>(new Set());
  const [apiReadyDocs, setApiReadyDocs] = useState<any[]>([]);

  useEffect(() => {
    let isMounted = true;
    sourceService
      .getDocuments()
      .then((res) => {
        if (!isMounted || !res.data) return;
        const docs = Array.isArray(res.data) ? res.data : (res.data as any).documents || [];
        setApiReadyDocs(docs);
        const readyNames = new Set<string>();
        docs.forEach((d: any) => {
          const name = d.filename || d.name;
          if (name && (d.status === 'ready' || d.status === 'indexed')) {
            readyNames.add(name.toLowerCase());
          }
        });
        setApiReadyFilenames(readyNames);
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const getEffectiveSessionId = useCallback(() => {
    return activeSessionIdRef?.current ?? currentSessionId ?? null;
  }, [activeSessionIdRef, currentSessionId]);

  const syncSourcesWithSession = useCallback(
    (updated: SourceDocument[]) => {
      const effId = getEffectiveSessionId();
      if (effId && effId !== 'new') {
        const activeIds = updated.filter((d) => d.selected).map((d) => d.id);
        const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === effId
              ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
              : s
          )
        );
      } else {
        try {
          localStorage.setItem(DRAFT_SOURCES_STORAGE_KEY, JSON.stringify(updated));
        } catch {}
      }
    },
    [getEffectiveSessionId, setSessions]
  );

  const handleToggleDocSelection = useCallback(
    (id: string) => {
      setSourceDocs((prev) => {
        const updated = prev.map((doc) =>
          doc.id === id ? { ...doc, selected: !doc.selected } : doc
        );
        syncSourcesWithSession(updated);
        const effId = getEffectiveSessionId();
        if (effId && effId !== 'new') {
          const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
          chatService.updateSessionDrawer?.(effId, activeNames).catch(() => {});
        }
        return updated;
      });
    },
    [getEffectiveSessionId, syncSourcesWithSession]
  );

  const handleSelectAllDocs = useCallback(() => {
    setSourceDocs((prev) => {
      const updated = prev.map((doc) => ({ ...doc, selected: true }));
      syncSourcesWithSession(updated);
      const effId = getEffectiveSessionId();
      if (effId && effId !== 'new') {
        const activeNames = updated.map((d) => d.name);
        chatService.updateSessionDrawer?.(effId, activeNames).catch(() => {});
      }
      return updated;
    });
  }, [getEffectiveSessionId, syncSourcesWithSession]);

  const handleDeselectAllDocs = useCallback(() => {
    setSourceDocs((prev) => {
      const updated = prev.map((doc) => ({ ...doc, selected: false }));
      syncSourcesWithSession(updated);
      const effId = getEffectiveSessionId();
      if (effId && effId !== 'new') {
        chatService.updateSessionDrawer?.(effId, []).catch(() => {});
      }
      return updated;
    });
  }, [getEffectiveSessionId, syncSourcesWithSession]);

  const handleRemoveSource = useCallback(
    (id: string) => {
      setSourceDocs((prev) => {
        const docToRemove = prev.find((d) => d.id === id);
        const updated = prev.filter((doc) => doc.id !== id);
        syncSourcesWithSession(updated);
        const effId = getEffectiveSessionId();
        if (effId && effId !== 'new' && docToRemove) {
          chatService.removeFromSessionDrawer?.(effId, docToRemove.name).catch(() => {});
        }
        return updated;
      });
    },
    [getEffectiveSessionId, syncSourcesWithSession]
  );

  const handleSelectLibraryDocument = useCallback(
    (item: LibraryItem) => {
      const filename = item.name;
      const sz = item.size || (item.bytes ? formatBytes(item.bytes) : '1.0 MB');
      const isProcessing = item.status === 'processing' || (item.uploadProgress !== undefined && item.uploadProgress < 100);
      const newDoc: SourceDocument = {
        id: item.id || `lib-${Date.now()}`,
        name: filename,
        size: sz,
        bytes: item.bytes,
        pages: (item as any).pages || 1,
        color: filename.toLowerCase().endsWith('.pdf') ? 'rose' : 'indigo',
        selected: true,
        status: isProcessing ? 'processing' : 'ready',
        uploadProgress: item.uploadProgress ?? (isProcessing ? 50 : 100),
      };

      setSourceDocs((prev) => {
        const exists = prev.some(
          (d) => d.name.toLowerCase() === filename.toLowerCase() || d.id === newDoc.id
        );
        let updated: SourceDocument[];
        if (exists) {
          updated = prev.map((d) =>
            d.name.toLowerCase() === filename.toLowerCase() || d.id === newDoc.id
              ? { ...d, selected: true }
              : d
          );
        } else {
          updated = [...prev, newDoc];
        }

        syncSourcesWithSession(updated);
        const effId = getEffectiveSessionId();
        if (effId && effId !== 'new') {
          chatService.attachToSessionDrawer?.(effId, filename).catch(() => {});
        }
        return updated;
      });
    },
    [getEffectiveSessionId, syncSourcesWithSession]
  );

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        const files = Array.from(e.target.files);
        // Clear input value so re-uploading the exact same document triggers change
        e.target.value = '';

        const newDocs: SourceDocument[] = files.map((file, idx) => ({
          id: `src-${Date.now()}-${idx}`,
          name: file.name,
          size: formatBytes(file.size),
          bytes: file.size,
          pages: 1,
          color: file.name.toLowerCase().endsWith('.pdf') ? 'rose' : 'indigo',
          selected: true,
          status: 'processing',
          uploadProgress: 18,
        }));

        setSourceDocs((prev) => {
          const updated = [...prev, ...newDocs];
          syncSourcesWithSession(updated);
          return updated;
        });

        const newDocIds = new Set(newDocs.map((d) => d.id));
        const fileNames = files.map((f) => f.name);

        // Smooth ingestion phase progress simulation while backend parses, chunks, and creates graph
        let currentPct = 18;
        const progressTimer = setInterval(() => {
          currentPct = Math.min(94, currentPct + Math.floor(Math.random() * 8) + 4);
          setSourceDocs((prev) =>
            prev.map((d) => (newDocIds.has(d.id) ? { ...d, uploadProgress: currentPct } : d))
          );
        }, 500);

        try {
          const effId = getEffectiveSessionId();
          const res = await sourceService.uploadPdfs(files, undefined, {
            sessionId: effId || undefined,
          });

          clearInterval(progressTimer);

          if (res.error || !res.data || res.data.status === 'error') {
            throw new Error(res.error?.message || (res.data as any)?.message || 'Ingestion failed');
          }

          setSourceDocs((prev) => {
            const updated = prev.map((d): SourceDocument =>
              newDocIds.has(d.id)
                ? { ...d, uploadProgress: 100, status: 'ready' as const, selected: true }
                : d
            );
            syncSourcesWithSession(updated);
            if (effId && effId !== 'new') {
              fileNames.forEach((fn) => {
                chatService.attachToSessionDrawer?.(effId, fn).catch(() => {});
              });
            }
            return updated;
          });

          setApiReadyFilenames((prev) => {
            const next = new Set(prev);
            fileNames.forEach((fn) => next.add(fn.toLowerCase()));
            return next;
          });
        } catch {
          clearInterval(progressTimer);
          setSourceDocs((prev) => {
            const updated = prev.map((d): SourceDocument =>
              newDocIds.has(d.id) ? { ...d, status: 'failed' as const, uploadProgress: 0 } : d
            );
            syncSourcesWithSession(updated);
            return updated;
          });
        }
      }
    },
    [getEffectiveSessionId, syncSourcesWithSession]
  );

  return {
    sourceDocs,
    setSourceDocs,
    isSourcesDrawerOpen,
    setIsSourcesDrawerOpen,
    isLibraryPickerOpen,
    setIsLibraryPickerOpen,
    apiReadyFilenames,
    setApiReadyFilenames,
    apiReadyDocs,
    setApiReadyDocs,
    handleToggleDocSelection,
    handleSelectAllDocs,
    handleDeselectAllDocs,
    handleRemoveSource,
    handleSelectLibraryDocument,
    handleFileUpload,
  };
}
