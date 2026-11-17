import type React from 'react';
import { useScrollLock } from '../../../hooks';
import { useDocumentViewerStore } from '../../../stores/useDocumentViewerStore';
import type { Citation } from '../../../types';
import { GoogleDrivePdfViewer } from '../../pdf-viewer/GoogleDrivePdfViewer';

export interface PdfViewerModalProps {
  isOpen?: boolean;
  citation?: Citation | null;
  onClose?: () => void;
}

// Sid says: Slide-over / modal dialog hosting Google Drive-style PDF viewer with zoom controls, page jumps, downloads, and search
export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  isOpen: propIsOpen,
  citation: propCitation,
  onClose: propOnClose,
}) => {
  const store = useDocumentViewerStore();

  const isModalOpen = Boolean(propIsOpen || store.isOpen);
  const storeTarget = store.target;

  useScrollLock(isModalOpen);

  if (!isModalOpen) {
    return null;
  }

  const resolvedFilename =
    storeTarget?.filename ||
    propCitation?.pdf_filename ||
    (propCitation as any)?.fileName ||
    (propCitation as any)?.filename ||
    (propCitation as any)?.name ||
    '';

  if (!resolvedFilename) {
    return null;
  }

  const resolvedPage =
    storeTarget?.pageNumber ||
    propCitation?.primary_page ||
    propCitation?.page_number ||
    (propCitation as any)?.page ||
    1;

  const resolvedExcerpt =
    storeTarget?.snippetText ||
    storeTarget?.excerpt ||
    propCitation?.plain_text ||
    (propCitation as any)?.excerpt ||
    (propCitation as any)?.snippet ||
    (propCitation as any)?.text ||
    '';

  const handleClose = () => {
    store.closeDocument();
    propOnClose?.();
  };

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center p-2 sm:p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={handleClose}
      data-testid="pdf-viewer-modal-backdrop"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`PDF Verification: ${resolvedFilename || 'Document'}`}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-6xl h-[94vh] bg-[#1e1e1e] text-slate-100 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
      >
        <GoogleDrivePdfViewer
          filename={resolvedFilename}
          initialPage={resolvedPage}
          excerpt={resolvedExcerpt}
          fileSize={storeTarget?.fileSize || (propCitation as any)?.fileSize || '2.4 MB'}
          onClose={handleClose}
        />
      </div>
    </div>
  );
};
