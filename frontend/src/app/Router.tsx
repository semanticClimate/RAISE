import type React from 'react';
import { lazy, Suspense } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppSkeleton } from '../components/ui/AppSkeleton';
import { RaisePage } from '../features/raise';

const PdfViewerPage = lazy(() =>
  import('../features/pdf-viewer/PdfViewerPage').then((module) => ({
    default: module.PdfViewerPage,
  }))
);

export const AppRouter: React.FC = () => {
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
