import {
  ArrowLeft,
  ExternalLink,
  FileText,
  RotateCw,
  X,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { sourceService } from '../../services/SourceService';

export interface GoogleDrivePdfViewerProps {
  filename: string;
  initialPage?: number;
  totalPages?: number;
  fileSize?: string;
  excerpt?: string;
  onClose?: () => void;
  isStandalone?: boolean;
}

/**
 * Clean, full-bleed PDF viewer embedding the browser's native PDF viewing engine
 * without duplicate custom floating toolbars, fake page counts, or redundant controls.
 */
export const GoogleDrivePdfViewer: React.FC<GoogleDrivePdfViewerProps> = ({
  filename,
  initialPage = 1,
  onClose,
  isStandalone = false,
}) => {
  const [loadError, setLoadError] = useState<boolean>(!filename);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const safePage = Math.max(1, initialPage);
  const targetPdfUrl = useMemo(
    () => (filename ? sourceService.getPdfUrl(filename, safePage) : ''),
    [filename, safePage]
  );

  // Probe target URL to proactively catch 404 or backend unavailable
  useEffect(() => {
    if (!filename) {
      setLoadError(true);
      return;
    }
    setLoadError(false);
    let cancelled = false;

    fetch(targetPdfUrl, { method: 'HEAD' })
      .then((res) => {
        if (cancelled) return;
        // Proactively flag only if file is genuinely not found (404)
        if (res.status === 404) {
          setLoadError(true);
        }
      })
      .catch(() => {
        // Network or CORS probe error - allow iframe attempt
      });

    return () => {
      cancelled = true;
    };
  }, [targetPdfUrl, filename]);

  // Keyboard shortcut listener: Esc closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (onClose && !isStandalone) {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isStandalone]);

  const handleOpenStandaloneTab = () => {
    if (!targetPdfUrl) return;
    window.open(targetPdfUrl, '_blank', 'noopener,noreferrer');
    if (!isStandalone && onClose) {
      onClose();
    }
  };

  return (
    <div
      className="flex flex-col w-full h-full bg-[#1e1e1e] text-slate-100 font-sans select-none overflow-hidden relative"
      data-testid="google-drive-pdf-viewer"
    >
      {/* ─── SLEEK, UNIFIED MODAL HEADER ─── */}
      <header className="h-12 z-40 px-4 flex items-center justify-between bg-[#1e1e1e] border-b border-white/10 shrink-0">
        {/* Left: Document Info */}
        <div className="flex items-center gap-3 text-white min-w-0 pr-2">
          {!isStandalone && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/15 text-slate-300 hover:text-white transition-colors cursor-pointer shrink-0"
              title="Close (Esc)"
              aria-label="Back"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}

          <div className="w-7 h-7 rounded-lg bg-white/10 text-white border border-white/20 flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4" />
          </div>

          <div className="min-w-0">
            <h1
              className="text-sm font-semibold text-white truncate leading-snug cursor-default"
              title={filename}
            >
              {filename}
            </h1>
            {safePage > 1 && (
              <span className="text-[11px] font-mono text-slate-400">
                Opening at Page {safePage}
              </span>
            )}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2 text-white shrink-0">
          <button
            type="button"
            onClick={handleOpenStandaloneTab}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/15 transition-colors cursor-pointer flex items-center gap-1.5 text-xs font-medium"
            title="Open in new browser tab"
            aria-label="Open in new tab"
          >
            <ExternalLink className="w-4 h-4" />
            <span className="hidden sm:inline">New Tab</span>
          </button>

          {!isStandalone && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/15 transition-colors cursor-pointer"
              title="Close (Esc)"
              aria-label="Close viewer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>

      {/* ─── FULL-BLEED NATIVE PDF DISPLAY CANVAS ─── */}
      <main className="flex-1 w-full h-full bg-[#525659] relative overflow-hidden flex items-center justify-center">
        {!loadError ? (
          <iframe
            ref={iframeRef}
            src={targetPdfUrl}
            title={`PDF Viewer: ${filename}`}
            onError={() => setLoadError(true)}
            className="w-full h-full border-0 block bg-[#525659]"
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-8 text-center max-w-md animate-in fade-in duration-200">
            <div className="w-12 h-12 rounded-2xl bg-white/10 text-slate-300 border border-white/20 flex items-center justify-center mb-4">
              <FileText className="w-6 h-6" />
            </div>
            <h2 className="text-base font-semibold text-white mb-2">
              {filename ? 'Document Preview Unavailable' : 'No Document Selected'}
            </h2>
            <p className="text-xs text-slate-400 mb-6 leading-relaxed">
              {filename
                ? `The document "${filename}" could not be previewed directly inline. You can retry or open the direct document.`
                : 'Please select a document to preview.'}
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setLoadError(false)}
                className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-medium text-white transition-colors cursor-pointer flex items-center gap-2"
              >
                <RotateCw className="w-3.5 h-3.5" />
                Retry
              </button>
              <button
                type="button"
                onClick={handleOpenStandaloneTab}
                className="px-4 py-2 rounded-xl bg-white text-black hover:bg-slate-200 text-xs font-semibold transition-colors cursor-pointer flex items-center gap-2 shadow-xs"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Direct PDF
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default GoogleDrivePdfViewer;
