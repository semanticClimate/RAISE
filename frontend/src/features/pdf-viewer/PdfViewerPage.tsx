import React, { useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { sourceService } from '../../services/SourceService';

// Sid says: Opens PDF directly in browser default PDF viewer without duplicate custom toolbars
export const PdfViewerPage: React.FC = () => {
  const location = useLocation();

  const { filename, page } = useMemo(() => {
    try {
      // Parse from search params or hash query
      const searchParams = new URLSearchParams(location.search);
      const hash = window.location.hash || '';
      const hashQuery = hash.includes('?') ? hash.substring(hash.indexOf('?')) : '';
      const hashParams = new URLSearchParams(hashQuery);

      const getParam = (key: string): string | null =>
        searchParams.get(key) || hashParams.get(key);

      const rawFile = getParam('file') || getParam('filename') || 'Document.pdf';
      const p = parseInt(getParam('page') || '1', 10) || 1;

      // Safe decode utility: URLSearchParams already decodes %20, %25, etc.
      // Calling decodeURIComponent again on strings containing literal '%' (like "84.6% of")
      // triggers a URIError: URI malformed crash. This helper guarantees safe recovery.
      const safeDecode = (val: string | null): string => {
        if (!val) return '';
        try {
          if (/%[0-9a-fA-F]{2}/.test(val)) {
            return decodeURIComponent(val);
          }
          return val;
        } catch {
          return val;
        }
      };

      const file = safeDecode(rawFile);
      return {
        filename: file,
        page: Math.max(1, p),
      };
    } catch {
      return {
        filename: 'Document.pdf',
        page: 1,
      };
    }
  }, [location]);

  const targetPdfUrl = sourceService.getPdfUrl(filename, page);

  // Immediately redirect to the native browser PDF viewer with default browser settings
  useEffect(() => {
    if (targetPdfUrl && typeof window !== 'undefined') {
      window.location.replace(targetPdfUrl);
    }
  }, [targetPdfUrl]);

  return (
    <div className="w-screen h-screen overflow-hidden bg-black m-0 p-0">
      <iframe
        src={targetPdfUrl}
        title={filename}
        className="w-full h-full border-0 block"
      />
    </div>
  );
};

export default PdfViewerPage;
