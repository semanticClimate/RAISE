import type React from 'react';
import { Suspense, lazy } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppSkeleton } from '../components/ui/AppSkeleton';

const RaisePage = lazy(() =>
  import('../features/raise').then((module) => ({ default: module.RaisePage }))
);

export const AppRouter: React.FC = () => {
  return (
    <HashRouter>
      <Suspense fallback={<AppSkeleton />}>
        <Routes>
          <Route path="/" element={<RaisePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </HashRouter>
  );
};

