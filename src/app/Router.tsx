import type React from 'react';
import { Suspense, lazy } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { WorkstationSkeleton } from '../components/ui/WorkstationSkeleton';

const RaisePage = lazy(() =>
  import('../features/raise').then((module) => ({ default: module.RaisePage }))
);

export const AppRouter: React.FC = () => {
  return (
    <HashRouter>
      <Suspense fallback={<WorkstationSkeleton />}>
        <Routes>
          <Route path="/" element={<RaisePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </HashRouter>
  );
};

