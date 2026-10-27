import type React from 'react';
import { lazy, Suspense, useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppSkeleton } from '../components/ui/AppSkeleton';
import { useControlCenterStore } from '../features/control-center/store/useControlCenterStore';

import { RaisePage } from '../features/raise';

const PdfViewerPage = lazy(() =>
  import('../features/pdf-viewer/PdfViewerPage').then((module) => ({
    default: module.PdfViewerPage,
  }))
);

export const AppRouter: React.FC = () => {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      // 1. Detect explicit ?setup=true or ?control_center=true from standard query or hash routing
      const urlParams = new URLSearchParams(window.location.search);
      const hash = window.location.hash || '';
      const hashQuery = hash.includes('?') ? hash.substring(hash.indexOf('?')) : '';
      const hashParams = new URLSearchParams(hashQuery);

      const isExplicitSetup =
        urlParams.get('setup') === 'true' ||
        urlParams.get('control_center') === 'true' ||
        hashParams.get('setup') === 'true' ||
        hashParams.get('control_center') === 'true';

      // 2. Detect first-time visit via localStorage
      const hasCompletedOnboarding =
        localStorage.getItem('raise_onboarding_completed') === 'true';

      const store = useControlCenterStore.getState();
      const isLocalMode =
        store.config.llmDeployment === 'local' ||
        store.config.llmMode?.startsWith('local_') ||
        Boolean(store.config.selectedLocalModel);

      if (isExplicitSetup || (!hasCompletedOnboarding && !store.config.firstRunCompleted && !isLocalMode)) {
        store.setOpen(true);
        const hasKey = store.config.apiKeys?.some(
          (k) => k.key && k.key.trim().length > 0 && k.provider !== 'unknown'
        );
        if (!hasKey) {
          store.setActiveTab('models');
        }
      }
    } catch {
      // Graceful fallback for restricted browser storage sandboxes
    }
  }, []);

  return (
    <HashRouter>
      <Suspense fallback={<AppSkeleton />}>
        <Routes>
          <Route path="/" element={<RaisePage />} />
          <Route path="/viewer" element={<PdfViewerPage />} />
          <Route path="/pdf-viewer" element={<PdfViewerPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </HashRouter>
  );
};
