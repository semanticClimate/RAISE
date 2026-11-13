import { create } from 'zustand';

export interface DocumentTarget {
  filename: string;
  pageNumber?: number;
  snippetText?: string;
  excerpt?: string;
  fileSize?: string;
}

interface DocumentViewerState {
  isOpen: boolean;
  target: DocumentTarget | null;
  openDocument: (filename: string, pageNumber?: number, snippetText?: string) => void;
  closeDocument: () => void;
  jumpToPage: (pageNumber: number) => void;
}

/**
 * Isolated Zustand store for orchestrating document viewing, citation verification,
 * and page navigation completely decoupled from the chat conversation and query box.
 */
export const useDocumentViewerStore = create<DocumentViewerState>((set) => ({
  isOpen: false,
  target: null,
  openDocument: (filename, pageNumber = 1, snippetText = '') => {
    const cleanName = (filename || '').trim();
    if (!cleanName || cleanName === 'Audited Document') return;
    set({
      isOpen: true,
      target: {
        filename: cleanName,
        pageNumber: Math.max(1, pageNumber || 1),
        snippetText: snippetText || '',
      },
    });
  },
  closeDocument: () => set({ isOpen: false, target: null }),
  jumpToPage: (pageNumber) =>
    set((state) => ({
      target: state.target ? { ...state.target, pageNumber: Math.max(1, pageNumber) } : null,
    })),
}));
