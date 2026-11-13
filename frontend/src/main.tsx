import '@total-typescript/ts-reset';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import { cleanseLegacyStorage } from './utils/storageCleaner';
import './styles/globals.css';
import 'katex/dist/katex.min.css';

// Purge any stale legacy sessions from browser storage on startup
cleanseLegacyStorage();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
