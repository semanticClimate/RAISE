import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { documentsQueryOptions } from '../api/queryOptions';
import { sourceService } from '../services/SourceService';
import { useModeStore } from '../stores/modeStore';
import type { DocumentItem } from '../types';

export interface UseDocumentLibraryOptions {
  enabled?: boolean;
}

/**
 * Modern React Query v5 hook for Document Library operations.
 * Provides cached document list queries, auto-invalidation on uploads and deletions,
 * and optimistic UI updates for the Knowledge Vault.
 */
export function useDocumentLibrary(options: UseDocumentLibraryOptions = {}) {
  const { enabled = true } = options;
  const isConnected = useModeStore((s) => s.appMode === 'connected' || s.appMode === 'degraded');
  const queryClient = useQueryClient();

  const documentsQuery = useQuery({
    ...documentsQueryOptions(),
    enabled: enabled && isConnected,
  });

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
      const res = await sourceService.uploadPdfs(files, undefined, {
        parseMode: mode,
        parser,
        sessionId,
      });
      if (res.error) {
        throw new Error(res.error.message);
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
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  const refreshDocuments = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['documents'] });
  }, [queryClient]);

  return {
    documents: (documentsQuery.data ?? []) as DocumentItem[],
    isLoading: documentsQuery.isLoading,
    isRefetching: documentsQuery.isRefetching,
    isError: documentsQuery.isError,
    error: documentsQuery.error,
    refreshDocuments,
    uploadDocuments: uploadMutation.mutateAsync,
    isUploading: uploadMutation.isPending,
    uploadError: uploadMutation.error,
    deleteDocument: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    deleteError: deleteMutation.error,
  };
}
