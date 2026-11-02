import type React from 'react';
import { useScrollLock } from '../../../hooks';
import type { Citation } from '../../../types';
import { GoogleDrivePdfViewer } from '../../pdf-viewer/GoogleDrivePdfViewer';

export interface PdfViewerModalProps {
  isOpen: boolean;
  citation: Citation | null;
  onClose: () => void;
}

// Sid says: Slide-over / modal dialog hosting Google Drive-style PDF viewer with zoom controls, page jumps, downloads, and search
export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  isOpen,
  citation,
  onClose,
}) => {
  useScrollLock(isOpen);

  if (!isOpen || !citation) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center p-2 sm:p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
      data-testid="pdf-viewer-modal-backdrop"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`PDF Verification: ${citation.pdf_filename}`}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-6xl h-[94vh] bg-[#1e1e1e] text-slate-100 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
      >
        <GoogleDrivePdfViewer
          filename={citation.pdf_filename || 'Audited Document'}
          initialPage={citation.primary_page || citation.page_number || 1}
          excerpt={citation.plain_text || (citation as any).excerpt || (citation as any).text || ''}
          fileSize="2.4 MB"
          onClose={onClose}
        />
      </div>
    </div>
  );
};
