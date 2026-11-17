import { useCallback, useState } from 'react';
import { sourceService } from '../services/SourceService';
import type { UploadResponse } from '../types';

export interface UseDocumentVaultOptions {
  onUploadSuccess?: (files: File[], res: UploadResponse) => void;
  onUploadError?: (files: File[], error: string) => void;
}

export interface UseDocumentVaultResult {
  isUploading: boolean;
  uploadProgress: Record<string, number>;
  uploadFiles: (
    files: File[],
    options?: { parseMode?: 'fast' | 'expert'; sessionId?: string }
  ) => Promise<UploadResponse | null>;
}

/**
 * useDocumentVault:
 * Custom hook to encapsulate file upload queues, asymptotic ingestion progress,
 * and manifest persistence.
 */
export function useDocumentVault(options?: UseDocumentVaultOptions): UseDocumentVaultResult {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});

  const uploadFiles = useCallback(
    async (
      files: File[],
      uploadOptions?: { parseMode?: 'fast' | 'expert'; sessionId?: string }
    ): Promise<UploadResponse | null> => {
      if (!files || files.length === 0) return null;
      setIsUploading(true);

      // Initialize progress
      const initialMap: Record<string, number> = {};
      files.forEach((f) => {
        initialMap[f.name] = 15;
      });
      setUploadProgress((prev) => ({ ...prev, ...initialMap }));

      // Asymptotic progress animation
      let currentPercent = 15;
      const timer = setInterval(() => {
        const step =
          currentPercent < 50
            ? Math.floor(Math.random() * 6) + 3
            : currentPercent < 75
              ? Math.floor(Math.random() * 3) + 2
              : currentPercent < 90
                ? 1
                : 0.2;
        currentPercent = Math.min(92, Number((currentPercent + step).toFixed(1)));
        setUploadProgress((prev) => {
          const updated = { ...prev };
          files.forEach((f) => {
            if (updated[f.name] !== undefined && updated[f.name] < 92) {
              updated[f.name] = Math.round(currentPercent);
            }
          });
          return updated;
        });
      }, 400);

      try {
        const res = await sourceService.uploadPdfs(files, undefined, {
          parseMode: uploadOptions?.parseMode || 'expert',
          parser: uploadOptions?.parseMode === 'fast' ? 'fast' : 'docling',
          sessionId: uploadOptions?.sessionId,
        });

        clearInterval(timer);

        if (res.error || res.status >= 400 || !res.data) {
          const errMsg = res.error?.message || 'Document ingestion failed.';
          setUploadProgress((prev) => {
            const updated = { ...prev };
            files.forEach((f) => {
              updated[f.name] = 0;
            });
            return updated;
          });
          options?.onUploadError?.(files, errMsg);
          return null;
        }

        setUploadProgress((prev) => {
          const updated = { ...prev };
          files.forEach((f) => {
            updated[f.name] = 100;
          });
          return updated;
        });

        options?.onUploadSuccess?.(files, res.data);
        return res.data;
      } catch (err) {
        clearInterval(timer);
        const errMsg = err instanceof Error ? err.message : String(err);
        options?.onUploadError?.(files, errMsg);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    [options]
  );

  return {
    isUploading,
    uploadProgress,
    uploadFiles,
  };
}
