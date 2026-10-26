import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { GoogleDrivePdfViewer } from './GoogleDrivePdfViewer';

// Sid says: Standalone full-window Google Drive PDF viewer route launched when opening citations in a new tab
export const PdfViewerPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const { filename, page, excerpt, fileSize, totalPages } = useMemo(() => {
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
      const rawExc = getParam('excerpt') || '';
      const rawSize = getParam('size');
      const rawTotal = getParam('total') || getParam('totalPages');

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
      const exc = safeDecode(rawExc);

      let total = parseInt(rawTotal || '', 10);
      if (!total || Number.isNaN(total)) {
        if (file.includes('Institutional')) {
          total = 32;
        } else if (file.includes('Biomimetic')) {
          total = 18;
        } else {
          total = 24;
        }
      }

      let size = rawSize || '';
      if (!size) {
        if (file.includes('Institutional')) {
          size = '4.1 MB';
        } else if (file.includes('Biomimetic')) {
          size = '2.4 MB';
        } else {
          size = '2.4 MB';
        }
      }

      return {
        filename: file,
        page: Math.max(1, p),
        excerpt: exc,
        fileSize: size,
        totalPages: total,
      };
    } catch {
      return {
        filename: 'Institutional_Research_Audit_2026.pdf',
        page: 12,
        excerpt: '',
        fileSize: '4.1 MB',
        totalPages: 32,
      };
    }
  }, [location]);

  const handleClose = () => {
    if (window.opener) {
      window.close();
    } else {
      navigate('/');
    }
  };

  return (
    <div className="w-screen h-screen overflow-hidden bg-[#1e1e1e]">
      <GoogleDrivePdfViewer
        filename={filename}
        initialPage={page}
        totalPages={totalPages}
        fileSize={fileSize}
        excerpt={excerpt}
        onClose={handleClose}
        isStandalone={true}
      />
    </div>
  );
};

export default PdfViewerPage;
