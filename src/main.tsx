import '@total-typescript/ts-reset';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import { cleanseLegacyMockStorage } from './utils/legacyMockCleanser';
import './styles/globals.css';

// Purge any stale legacy mock sessions from browser storage on startup
cleanseLegacyMockStorage();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
