import { useCallback, useState } from 'react';
import type { LibraryItem } from '../../../components/settings/SettingsLibraryTab';
import { chatService } from '../../../services/ChatService';
import { sourceService } from '../../../services/SourceService';
import { formatBytes } from '../../../utils/formatters';
import type { ChatSession, SourceDocument } from '../types';

export interface UseSessionSourcesOptions {
  currentSessionId: string | null;
  setSessions: React.Dispatch<React.SetStateAction<ChatSession[]>>;
}

export function useSessionSources({ currentSessionId, setSessions }: UseSessionSourcesOptions) {
  const [sourceDocs, setSourceDocs] = useState<SourceDocument[]>([]);
  const [isSourcesDrawerOpen, setIsSourcesDrawerOpen] = useState(false);
  const [isLibraryPickerOpen, setIsLibraryPickerOpen] = useState(false);
  const [apiReadyFilenames, setApiReadyFilenames] = useState<Set<string>>(new Set());
  const [apiReadyDocs, setApiReadyDocs] = useState<any[]>([]);

  const handleToggleDocSelection = useCallback((id: string) => {
    setSourceDocs((prev) => {
      const updated = prev.map((doc) =>
        doc.id === id ? { ...doc, selected: !doc.selected } : doc
      );
      if (currentSessionId) {
        const activeIds = updated.filter((d) => d.selected).map((d) => d.id);
        const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === currentSessionId
              ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
              : s
          )
        );
        chatService.updateSessionDrawer?.(currentSessionId, activeNames).catch(() => {});
      }
      return updated;
    });
  }, [currentSessionId, setSessions]);

  const handleSelectAllDocs = useCallback(() => {
    setSourceDocs((prev) => {
      const updated = prev.map((doc) => ({ ...doc, selected: true }));
      if (currentSessionId) {
        const activeIds = updated.map((d) => d.id);
        const activeNames = updated.map((d) => d.name);
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === currentSessionId
              ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
              : s
          )
        );
        chatService.updateSessionDrawer?.(currentSessionId, activeNames).catch(() => {});
      }
      return updated;
    });
  }, [currentSessionId, setSessions]);

  const handleDeselectAllDocs = useCallback(() => {
    setSourceDocs((prev) => {
      const updated = prev.map((doc) => ({ ...doc, selected: false }));
      if (currentSessionId) {
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === currentSessionId
              ? { ...s, selectedSourceIds: [], sources: updated, attached_docs: [] }
              : s
          )
        );
        chatService.updateSessionDrawer?.(currentSessionId, []).catch(() => {});
      }
      return updated;
    });
  }, [currentSessionId, setSessions]);

  const handleRemoveSource = useCallback((id: string) => {
    setSourceDocs((prev) => {
      const docToRemove = prev.find((d) => d.id === id);
      const updated = prev.filter((doc) => doc.id !== id);
      if (currentSessionId && docToRemove) {
        const activeIds = updated.filter((d) => d.selected).map((d) => d.id);
        const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === currentSessionId
              ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
              : s
          )
        );
        chatService.removeFromSessionDrawer?.(currentSessionId, docToRemove.name).catch(() => {});
      }
      return updated;
    });
  }, [currentSessionId, setSessions]);

  const handleSelectLibraryDocument = useCallback((item: LibraryItem) => {
    const filename = item.name;
    const sz = item.size || (item.bytes ? formatBytes(item.bytes) : '1.0 MB');
    const newDoc: SourceDocument = {
      id: item.id || `lib-${Date.now()}`,
      name: filename,
      size: sz,
      bytes: item.bytes,
      pages: (item as any).pages || 1,
      color: filename.endsWith('.pdf') ? 'rose' : 'indigo',
      selected: true,
      status: 'ready',
    };

    setSourceDocs((prev) => {
      const exists = prev.some(
        (d) => d.name.toLowerCase() === filename.toLowerCase() || d.id === newDoc.id
      );
      if (exists) {
        return prev.map((d) =>
          d.name.toLowerCase() === filename.toLowerCase() || d.id === newDoc.id
            ? { ...d, selected: true }
            : d
        );
      }
      const updated = [...prev, newDoc];
      if (currentSessionId) {
        const activeIds = updated.filter((d) => d.selected).map((d) => d.id);
        const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
        setSessions((prevSessions) =>
          prevSessions.map((s) =>
            s.id === currentSessionId
              ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
              : s
          )
        );
        chatService.attachToSessionDrawer?.(currentSessionId, filename).catch(() => {});
      }
      return updated;
    });
  }, [currentSessionId, setSessions]);

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        const tempDocId = `src-${Date.now()}`;
        const newDoc: SourceDocument = {
          id: tempDocId,
          name: file.name,
          size: formatBytes(file.size),
          bytes: file.size,
          pages: 1,
          color: file.name.endsWith('.pdf') ? 'rose' : 'indigo',
          selected: true,
          status: 'processing',
          uploadProgress: 15,
        };

        setSourceDocs((prev) => {
          const updated = [...prev, newDoc];
          if (currentSessionId) {
            const activeIds = updated.filter((d) => d.selected).map((d) => d.id);
            const activeNames = updated.filter((d) => d.selected).map((d) => d.name);
            setSessions((prevSessions) =>
              prevSessions.map((s) =>
                s.id === currentSessionId
                  ? { ...s, selectedSourceIds: activeIds, sources: updated, attached_docs: activeNames }
                  : s
              )
            );
          }
          return updated;
        });

        try {
          const res = await sourceService.uploadPdfs([file], undefined, {
            sessionId: currentSessionId || undefined,
          });
          const isImmediateReady = Boolean(res.data && res.data.uploaded_count > 0);
          const backendDocId = (res.data as any)?.id;

          const markReady = () => {
            setSourceDocs((prev) =>
              prev.map((d) =>
                d.id === tempDocId || d.name === file.name
                  ? { ...d, uploadProgress: 100, status: 'ready', selected: true }
                  : d
              )
            );
            setApiReadyFilenames((prev) => new Set([...prev, file.name.toLowerCase()]));

            if (currentSessionId && currentSessionId !== 'new') {
              chatService.attachToSessionDrawer?.(currentSessionId, file.name).catch(() => {});
            }
          };

          if (isImmediateReady) {
            markReady();
          } else if (backendDocId) {
            sourceService.watchDocumentIngestionEvents(
              backendDocId,
              (progStatus) => {
                const pct = Math.max(15, Math.min(100, progStatus.percent));
                setSourceDocs((prev) =>
                  prev.map((d) =>
                    d.id === tempDocId || d.name === file.name
                      ? {
                          ...d,
                          uploadProgress: pct,
                          status:
                            progStatus.status === 'ready' || pct >= 100 ? 'ready' : 'processing',
                        }
                      : d
                  )
                );
              },
              () => markReady(),
              () => markReady()
            );
          } else {
            markReady();
          }
        } catch {
          setSourceDocs((prev) =>
            prev.map((d) =>
              d.id === tempDocId ? { ...d, status: 'failed', uploadProgress: 0 } : d
            )
          );
        }
      }
    },
    [currentSessionId, setSessions]
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
