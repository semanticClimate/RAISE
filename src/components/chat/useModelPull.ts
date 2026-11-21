import { useState } from 'react';
import { platformAdapter } from '../../features/control-center/services/platformAdapter';
import { useControlCenterStore } from '../../features/control-center/store/useControlCenterStore';

export function useModelPull(modelName?: string) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<{
    percent: number;
    status: string;
  } | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDirectDownload = async () => {
    if (!modelName || isDownloading) return;
    setIsDownloading(true);
    setDownloadError(null);
    try {
      await platformAdapter.pullModel(modelName, (percent, statusText) => {
        setDownloadProgress({ percent, status: statusText });
      });
      setDownloadSuccess(true);
      useControlCenterStore.getState().syncBackendConfig();
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Download failed.';
      setDownloadError(`${errMsg} Please try downloading in Control Center.`);
    } finally {
      setIsDownloading(false);
    }
  };

  return {
    isDownloading,
    downloadProgress,
    downloadSuccess,
    downloadError,
    handleDirectDownload,
  };
}
