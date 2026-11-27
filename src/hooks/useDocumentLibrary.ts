import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { documentsQueryOptions } from '../api/queryOptions';
import { sourceService } from '../services/SourceService';
import { useModeStore } from '../stores/modeStore';
import type { DocumentItem, DocumentStatusResponse } from '../types';

export type IngestionStage =
  | 'uploading'
  | 'parsing'
  | 'chunking'
  | 'vectorizing'
  | 'graph_extraction'
  | 'completed'
  | 'error';

export interface IngestionStatusTransition {
  stage: IngestionStage;
  stageIndex: number; // 1 to 5 (0 for uploading/error)
  totalStages: number; // 5
  percent: number; // 0 to 100
  label: string;
  detail: string;
  statusText: string; // "parsing ➔ chunking ➔ vectorizing ➔ graph_extraction ➔ completed"
  breadcrumb: string; // e.g. "parsing ✓ ➔ [chunking] ➔ vectorizing ➔ graph_extraction ➔ completed"
  isCompleted: boolean;
  isError: boolean;
  error?: string;
  updatedAt: number;
}

export interface UseDocumentLibraryOptions {
  enabled?: boolean;
}

const CANONICAL_STAGES: IngestionStage[] = [
  'parsing',
  'chunking',
  'vectorizing',
  'graph_extraction',
  'completed',
];

const STAGE_LABELS: Record<IngestionStage, string> = {
  uploading: 'Uploading Document',
  parsing: 'Parsing Layout & Tables',
  chunking: 'Hierarchical Chunking (GGAHC)',
  vectorizing: 'Dense Vector Indexing (ChromaDB)',
  graph_extraction: 'Extracting Knowledge Graph',
  completed: 'Ingestion Completed',
  error: 'Ingestion Failed',
};

const STAGE_BASE_PERCENTS: Record<IngestionStage, number> = {
  uploading: 10,
  parsing: 25,
  chunking: 50,
  vectorizing: 75,
  graph_extraction: 90,
  completed: 100,
  error: 0,
};

/**
 * Builds canonical breadcrumb highlighting active stage:
 * "parsing ✓ ➔ [chunking] ➔ vectorizing ➔ graph_extraction ➔ completed"
 */
function buildBreadcrumb(stage: IngestionStage): string {
  if (stage === 'completed') {
    return 'parsing ✓ ➔ chunking ✓ ➔ vectorizing ✓ ➔ graph_extraction ✓ ➔ completed ✓';
  }
  if (stage === 'error') {
    return 'parsing ➔ chunking ➔ vectorizing ➔ graph_extraction ➔ completed (error)';
  }

  return CANONICAL_STAGES.map((s) => {
    if (s === stage) return `[${s}]`;
    const sIdx = CANONICAL_STAGES.indexOf(s);
    const currIdx = CANONICAL_STAGES.indexOf(stage);
    if (currIdx > -1 && sIdx < currIdx) return `${s} ✓`;
    return s;
  }).join(' ➔ ');
}

/**
 * Maps raw backend phase/status to canonical IngestionStatusTransition.
 */
function computeTransitionState(
  rawPhase?: string,
  rawStatus?: string,
  rawPercent?: number,
  rawDetail?: string
): IngestionStatusTransition {
  const normalized = (rawPhase || rawStatus || 'parsing').toLowerCase().trim();

  let stage: IngestionStage = 'parsing';
  if (normalized === 'uploading' || normalized === 'upload') {
    stage = 'uploading';
  } else if (normalized.includes('parse') || normalized === 'parsing') {
    stage = 'parsing';
  } else if (normalized.includes('chunk') || normalized === 'chunking') {
    stage = 'chunking';
  } else if (
    normalized.includes('embed') ||
    normalized.includes('vector') ||
    normalized === 'vectorizing' ||
    normalized === 'embedding'
  ) {
    stage = 'vectorizing';
  } else if (
    normalized.includes('graph') ||
    normalized.includes('relation') ||
    normalized.includes('entity') ||
    normalized === 'graph_extraction'
  ) {
    stage = 'graph_extraction';
  } else if (
    normalized.includes('complete') ||
    normalized.includes('ready') ||
    normalized === 'completed' ||
    normalized === 'ready'
  ) {
    stage = 'completed';
  } else if (
    normalized.includes('fail') ||
    normalized.includes('err') ||
    normalized === 'error' ||
    normalized === 'failed'
  ) {
    stage = 'error';
  }

  const basePct = STAGE_BASE_PERCENTS[stage];
  const percent =
    typeof rawPercent === 'number' && !Number.isNaN(rawPercent)
      ? Math.max(basePct, Math.min(100, Math.round(rawPercent)))
      : basePct;

  const stageIndex = stage === 'uploading' || stage === 'error'
    ? 0
    : CANONICAL_STAGES.indexOf(stage) + 1;

  const label = STAGE_LABELS[stage];
  const detail = rawDetail || label;
  const statusText = 'parsing ➔ chunking ➔ vectorizing ➔ graph_extraction ➔ completed';
  const breadcrumb = buildBreadcrumb(stage);

  return {
    stage,
    stageIndex,
    totalStages: 5,
    percent,
    label,
    detail,
    statusText,
    breadcrumb,
    isCompleted: stage === 'completed',
    isError: stage === 'error',
    error: stage === 'error' ? detail : undefined,
    updatedAt: Date.now(),
  };
}

/**
 * Modern React Query v5 hook for Document Library operations.
 * Subscribes to document.status transitions (parsing ➔ chunking ➔ vectorizing ➔ graph_extraction ➔ completed)
 * to provide granular progress bars and live ingestion monitoring for large institutional reports.
 */
export function useDocumentLibrary(options: UseDocumentLibraryOptions = {}) {
  const { enabled = true } = options;
  const isConnected = useModeStore((s) => s.appMode === 'connected' || s.appMode === 'degraded');
  const queryClient = useQueryClient();

  const [ingestionTransitions, setIngestionTransitions] = useState<
    Record<string, IngestionStatusTransition>
  >({});

  const activeSubscriptionsRef = useRef<Map<string, () => void>>(new Map());

  const documentsQuery = useQuery({
    ...documentsQueryOptions(),
    enabled: enabled && isConnected,
  });

  const updateDocumentProgress = useCallback(
    (
      key: string,
      phase?: string,
      status?: string,
      percent?: number,
      detail?: string
    ) => {
      setIngestionTransitions((prev) => {
        const nextState = computeTransitionState(phase, status, percent, detail);
        return {
          ...prev,
          [key]: nextState,
        };
      });
    },
    []
  );

  // Subscribe to live SSE events (/api/documents/{id}/events) for an actively ingesting document
  const subscribeToDocumentEvents = useCallback(
    (docIdOrFilename: string) => {
      if (!docIdOrFilename || activeSubscriptionsRef.current.has(docIdOrFilename)) {
        return;
      }

      const unsubscribe = sourceService.watchDocumentIngestionEvents(
        docIdOrFilename,
        (progress: DocumentStatusResponse) => {
          updateDocumentProgress(
            docIdOrFilename,
            progress.phase,
            progress.status,
            progress.percent,
            progress.detail
          );
        },
        () => {
          // Ingestion complete
          updateDocumentProgress(docIdOrFilename, 'completed', 'ready', 100, 'Ingestion Completed');
          queryClient.invalidateQueries({ queryKey: ['documents'] });
          activeSubscriptionsRef.current.delete(docIdOrFilename);
        },
        () => {
          // On SSE stream close or error, execute fallback poll
          sourceService
            .getDocumentStatus(docIdOrFilename)
            .then((res) => {
              if (res.data) {
                updateDocumentProgress(
                  docIdOrFilename,
                  res.data.phase,
                  res.data.status,
                  res.data.percent,
                  res.data.detail
                );
              }
            })
            .catch(() => {});
          activeSubscriptionsRef.current.delete(docIdOrFilename);
        }
      );

      activeSubscriptionsRef.current.set(docIdOrFilename, unsubscribe);
    },
    [queryClient, updateDocumentProgress]
  );

  // Automatically watch active documents from query results that are in non-ready states
  useEffect(() => {
    const rawDocs = (documentsQuery.data ?? []) as DocumentItem[];
    rawDocs.forEach((doc) => {
      const isProcessing =
        doc.status &&
        doc.status !== 'ready' &&
        doc.status !== 'completed' &&
        doc.status !== 'error' &&
        doc.status !== 'failed';
      const key = doc.id || doc.doc_id || doc.filename;

      if (isProcessing && key) {
        subscribeToDocumentEvents(key);
      }
    });
  }, [documentsQuery.data, subscribeToDocumentEvents]);

  // Clean up subscriptions on unmount
  useEffect(() => {
    const subs = activeSubscriptionsRef.current;
    return () => {
      subs.forEach((unsub) => {
        try {
          unsub();
        } catch {}
      });
      subs.clear();
    };
  }, []);

  const uploadMutation = useMutation({
    mutationFn: async ({
      files,
      mode = 'fast',
      parser = 'docling',
      sessionId,
    }: {
      files: File[];
      mode?: 'fast' | 'expert';
      parser?: string;
      sessionId?: string;
    }) => {
      // Immediately register initial transition for each file
      files.forEach((f) => {
        updateDocumentProgress(
          f.name,
          'uploading',
          'processing',
          15,
          'Streaming binary PDF to disk'
        );
      });

      const res = await sourceService.uploadPdfs(files, undefined, {
        parseMode: mode,
        parser,
        sessionId,
      });

      if (res.error) {
        files.forEach((f) => {
          updateDocumentProgress(f.name, 'error', 'failed', 0, res.error?.message || 'Upload failed');
        });
        throw new Error(res.error.message);
      }

      // If backend returned individual reports, transition each report
      const reports = (res.data as any)?.reports || [];
      if (Array.isArray(reports) && reports.length > 0) {
        reports.forEach((rep: any) => {
          const docKey = rep.doc_id || rep.document_id || rep.filename;
          if (docKey) {
            const isReady = rep.status === 'ready' || rep.status === 'success';
            if (isReady) {
              updateDocumentProgress(
                docKey,
                'completed',
                'ready',
                100,
                'Document successfully indexed and ready for GraphRAG research queries'
              );
            } else {
              subscribeToDocumentEvents(docKey);
            }
          }
        });
      } else {
        files.forEach((f) => {
          updateDocumentProgress(
            f.name,
            'completed',
            'ready',
            100,
            'Document successfully indexed and ready for GraphRAG research queries'
          );
        });
      }

      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (filenameOrId: string) => {
      const res = await sourceService.deleteDocument(filenameOrId);
      if (res.error) {
        throw new Error(res.error.message);
      }
      setIngestionTransitions((prev) => {
        const next = { ...prev };
        delete next[filenameOrId];
        return next;
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const refreshDocuments = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['documents'] });
  }, [queryClient]);

  // Merge live granular progress into each document item
  const documents = useMemo(() => {
    const rawDocs = (documentsQuery.data ?? []) as DocumentItem[];
    return rawDocs.map((doc) => {
      const key = doc.id || doc.doc_id || doc.filename;
      const transition =
        ingestionTransitions[key] ||
        ingestionTransitions[doc.filename] ||
        (doc.id ? ingestionTransitions[doc.id] : undefined);

      if (transition) {
        return {
          ...doc,
          status: transition.isCompleted ? 'ready' : transition.stage,
          phase: transition.stage,
          percent: transition.percent,
          progress_percent: transition.percent,
          progress_stage: transition.label,
          progress_detail: transition.detail,
          status_breadcrumb: transition.breadcrumb,
          is_ingesting: !transition.isCompleted && !transition.isError,
        };
      }
      return doc;
    });
  }, [documentsQuery.data, ingestionTransitions]);

  const getIngestionTransition = useCallback(
    (docIdOrFilename: string): IngestionStatusTransition | undefined => {
      return (
        ingestionTransitions[docIdOrFilename] ||
        Object.entries(ingestionTransitions).find(
          ([k]) => k.includes(docIdOrFilename) || docIdOrFilename.includes(k)
        )?.[1]
      );
    },
    [ingestionTransitions]
  );

  const hasActiveIngestions = useMemo(() => {
    return Object.values(ingestionTransitions).some((t) => !t.isCompleted && !t.isError);
  }, [ingestionTransitions]);

  return {
    documents,
    ingestionTransitions,
    getIngestionTransition,
    hasActiveIngestions,
    isLoading: documentsQuery.isLoading,
    isRefetching: documentsQuery.isRefetching,
    isError: documentsQuery.isError,
    error: documentsQuery.error,
    refreshDocuments,
    uploadDocuments: uploadMutation.mutateAsync,
    isUploading: uploadMutation.isPending || hasActiveIngestions,
    uploadError: uploadMutation.error,
    deleteDocument: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error,
  };
}
