import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen,
  Check,
  ExternalLink,
  FileText,
  Loader2,
  Plus,
  Search,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import type React from 'react';
import { useCallback, useMemo, useRef, useState } from 'react';
import { getApiBaseUrl } from '../../app/config';
import { documentsQueryOptions } from '../../api/queryOptions';
import { useEscapeKey, useScrollLock } from '../../hooks';
import { sourceService } from '../../services/SourceService';
import { documentItemToLibraryItem, type LibraryItem } from '../settings/SettingsLibraryTab';
import { ExtractedDocumentModal } from './ExtractedDocumentModal';

export interface OptimisticUploadItem {
  id: string;
  name: string;
  size: string;
  bytes: number;
  previewHash: string;
  progress: number;
  status: 'processing' | 'ready' | 'error';
  timestamp: number;
}

export interface LibraryPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectDocument: (doc: LibraryItem) => void;
  attachedDocNames: string[];
  onOpenUploadFromPC: () => void;
  onViewPdf?: (filename: string, pageNumber?: number) => void;
  onAttachAll?: (items: LibraryItem[]) => void;
  onDocumentDeleted?: (filename: string) => void;
}

export const LibraryPickerModal: React.FC<LibraryPickerModalProps> = ({
  isOpen,
  onClose,
  onSelectDocument,
  attachedDocNames,
  onOpenUploadFromPC,
  onAttachAll,
  onDocumentDeleted,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'pdf' | 'csv' | 'docx' | 'other'>('all');
  const [optimisticUploads, setOptimisticUploads] = useState<OptimisticUploadItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);
  const [artifactModal, setArtifactModal] = useState<{
    isOpen: boolean;
    documentName: string;
    type: 'markdown' | 'okf';
    url?: string;
  }>({
    isOpen: false,
    documentName: '',
    type: 'markdown',
  });
  const localFileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // TanStack Query v5 data fetching
  const { data: rawDocuments = [], isLoading } = useQuery({
    ...documentsQueryOptions(),
    enabled: isOpen,
    refetchOnMount: 'always',
    placeholderData: (prev) => prev,
  });

  const computePreviewHash = useCallback(async (file: File): Promise<string> => {
    try {
      if (typeof crypto !== 'undefined' && crypto.subtle) {
        const slice = file.slice(0, 32768);
        const buffer = await slice.arrayBuffer();
        const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
        return hex.slice(0, 10);
      }
    } catch {
      // Fallback
    }
    const clean = file.name.replace(/[^a-zA-Z0-9]/g, '');
    return `${clean.slice(0, 6)}-${file.size % 99999}`;
  }, []);

  const formatFileSize = (bytes: number): string => {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    if (bytes >= 1024) {
      return `${Math.round(bytes / 1024)} KB`;
    }
    return `${bytes} B`;
  };

  const handleOptimisticUpload = useCallback(
    async (selectedFiles: FileList | File[]) => {
      const files = Array.from(selectedFiles);
      if (files.length === 0) return;

      const newOptimistic: OptimisticUploadItem[] = [];

      for (const file of files) {
        const previewHash = await computePreviewHash(file);
        const optItem: OptimisticUploadItem = {
          id: `opt-${previewHash}-${Date.now()}`,
          name: file.name,
          size: formatFileSize(file.size),
          bytes: file.size,
          previewHash,
          progress: 18,
          status: 'processing',
          timestamp: Date.now(),
        };
        newOptimistic.push(optItem);
      }

      setOptimisticUploads((prev) => [...prev, ...newOptimistic]);

      try {
        const res = await sourceService.uploadPdfs(files);
        if (res.data) {
          queryClient.invalidateQueries({ queryKey: ['documents'] });
        }
      } catch (err) {
        console.error('Upload error in LibraryPickerModal:', err);
      } finally {
        setOptimisticUploads((prev) =>
          prev.filter((item) => !files.some((f) => f.name === item.name))
        );
      }
    },
    [computePreviewHash, queryClient]
  );

  const handleDeleteDocument = async (name: string) => {
    setDeletingName(name);
    try {
      // Optimistically remove from TanStack Query document cache
      queryClient.setQueryData(['documents'], (oldDocs: any) => {
        if (!Array.isArray(oldDocs)) return oldDocs;
        return oldDocs.filter(
          (d: any) => (d.filename || d.name) !== name && d.id !== name && d.doc_id !== name
        );
      });
      setOptimisticUploads((prev) => prev.filter((o) => o.name !== name));

      // Invoke authoritative backend purge (ChromaDB, Neo4j, PostgreSQL, filesystem, manifest)
      const res = await sourceService.deleteDocument(name);
      if (res.status === 403 || res.error) {
        // Rollback / re-synchronize on refusal or failure
        queryClient.invalidateQueries({ queryKey: ['documents'] });
        return;
      }

      // Authoritative cache refresh
      queryClient.invalidateQueries({ queryKey: ['documents'] });

      // Notify parent to unattach if document was in active session drawer
      if (onDocumentDeleted) {
        onDocumentDeleted(name);
      }
    } catch (err) {
      console.error('Delete error in LibraryPickerModal:', err);
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    } finally {
      setDeletingName(null);
    }
  };

  const handleOpenDocumentInNewTab = (item: LibraryItem) => {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    let targetUrl = sourceService.getPdfUrl(item.name);
    if (item.type !== 'pdf' && item.extracted_md_url) {
      targetUrl = `${base}${item.extracted_md_url}`;
    }
    window.open(targetUrl, '_blank', 'noopener,noreferrer');
  };

  const apiReadyFilenames = useMemo(() => {
    return new Set(
      rawDocuments
        .filter((d) => d.status === 'ready' || d.status === 'indexed')
        .map((d) => (d.filename || d.name || '').toLowerCase())
        .filter(Boolean)
    );
  }, [rawDocuments]);

  const isItemIndexed = useCallback(
    (item: LibraryItem): boolean => {
      if (item.status === 'processing') return false;
      if (item.uploadProgress !== undefined && item.uploadProgress < 100) return false;
      if (apiReadyFilenames.size > 0 && apiReadyFilenames.has(item.name.toLowerCase())) {
        return true;
      }
      return item.status === 'indexed' || item.status === 'ready';
    },
    [apiReadyFilenames]
  );

  // Authoritative list: ONLY show documents that are successfully parsed & ready
  const items = useMemo(() => {
    const backendItems = rawDocuments.map(documentItemToLibraryItem);
    return backendItems.filter(isItemIndexed);
  }, [rawDocuments, isItemIndexed]);

  useEscapeKey(onClose, isOpen && !artifactModal.isOpen);

  const attachedSet = useMemo(() => {
    return new Set(attachedDocNames.map((n) => n.toLowerCase().trim()));
  }, [attachedDocNames]);

  const filteredItems = useMemo(() => {
    let result = [...items];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((item) => item.name.toLowerCase().includes(q));
    }

    if (typeFilter !== 'all') {
      result = result.filter((item) => {
        if (typeFilter === 'other') {
          return !['pdf', 'csv', 'docx'].includes(item.type);
        }
        return item.type === typeFilter;
      });
    }

    return result;
  }, [items, searchQuery, typeFilter]);

  const unattachedReadyItems = useMemo(() => {
    return filteredItems.filter((item) => !attachedSet.has(item.name.toLowerCase().trim()));
  }, [filteredItems, attachedSet]);

  useScrollLock(isOpen);

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 z-[120] flex items-center justify-center p-3 sm:p-5 bg-[#000000]/40 backdrop-blur-md animate-in fade-in duration-150 select-none ${
        isDragOver ? 'ring-2 ring-[#FFFFFF]/50' : ''
      }`}
      onClick={onClose}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          handleOptimisticUpload(e.dataTransfer.files);
        }
      }}
    >
      <input
        ref={localFileInputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.docx,.csv,.md,.json,.xlsx"
        className="hidden"
        onClick={(e) => {
          (e.target as HTMLInputElement).value = '';
        }}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleOptimisticUpload(e.target.files);
            e.target.value = '';
          }
        }}
      />
      <div
        className="w-[min(94vw,40rem)] max-h-[88dvh] bg-[#0A0A0A] text-[#FFFFFF] border border-[#292929] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150 font-sans"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="library-picker-title"
      >
        {/* Header */}
        <div className="h-14 px-5 sm:px-6 border-b border-[#292929] bg-[#0A0A0A] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
              <BookOpen className="w-4 h-4 text-[#FFFFFF]" />
            </div>
            <div className="min-w-0">
              <h3
                id="library-picker-title"
                className="text-sm sm:text-base font-semibold text-[#FFFFFF] truncate"
              >
                Attach from Knowledge Base Library
              </h3>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-[#292929] shrink-0"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-[#FFFFFF]" />
          </button>
        </div>

        {/* Search & Actions Bar - Seamlessly merged without extra line */}
        <div className="pt-3.5 px-4 sm:px-6 pb-2 bg-[#0A0A0A] space-y-2.5 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="relative flex-1 min-w-0">
              <Search className="w-3.5 h-3.5 text-[#A3A3A3] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search library documents..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl bg-[#111111] border border-[#292929] text-[#FFFFFF] placeholder-[#A3A3A3] focus:outline-none focus:border-[#FFFFFF]/40 transition-all shadow-2xs"
              />
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => {
                  if (localFileInputRef.current) {
                    localFileInputRef.current.click();
                  } else {
                    onOpenUploadFromPC();
                  }
                }}
                className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] transition-all cursor-pointer whitespace-nowrap shrink-0 flex items-center gap-1.5 active:scale-95 shadow-xs"
                title="Add new document from PC to library"
              >
                <Plus className="w-3.5 h-3.5 text-[#000000] stroke-[2.2]" />
                <span className="hidden sm:inline">Add Document</span>
                <span className="sm:hidden font-medium">Add</span>
              </button>

              {onAttachAll && unattachedReadyItems.length > 0 && (
                <button
                  type="button"
                  onClick={() => onAttachAll(unattachedReadyItems)}
                  className="text-xs font-medium px-3 py-1.5 rounded-xl bg-[#171717] hover:bg-[#292929] border border-[#292929] text-[#FFFFFF] transition-all cursor-pointer whitespace-nowrap shrink-0 active:scale-95"
                  title="Attach all ready documents to current chat"
                  aria-label="Attach all ready documents"
                >
                  All
                </button>
              )}
            </div>
          </div>

          {/* Type Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
            {(['all', 'pdf', 'csv', 'docx', 'other'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTypeFilter(t)}
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono transition-colors whitespace-nowrap cursor-pointer ${
                  typeFilter === t
                    ? 'bg-[#FFFFFF] text-[#000000] font-semibold'
                    : 'bg-[#111111] text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] border border-[#292929]'
                }`}
              >
                {t === 'all' ? 'All' : t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Documents List */}
        <div
          className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-2.5 max-h-[50vh] bg-[#0A0A0A]"
          style={{ scrollbarWidth: 'thin' }}
        >
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-xs text-[#A3A3A3] gap-2.5">
              <Loader2 className="w-5 h-5 text-[#FFFFFF] animate-spin" />
              <span>Loading Knowledge Base Library...</span>
            </div>
          ) : filteredItems.length === 0 && optimisticUploads.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <div className="w-10 h-10 rounded-xl bg-[#171717] border border-[#292929] flex items-center justify-center text-[#A3A3A3] mb-3">
                <BookOpen className="w-5 h-5 text-[#A3A3A3]" />
              </div>
              <p className="text-xs sm:text-sm font-semibold text-[#FFFFFF] mb-1">
                {searchQuery ? 'No matching documents found' : 'No parsed documents in library'}
              </p>
              <p className="text-[11px] text-[#A3A3A3] max-w-xs mb-4">
                {searchQuery
                  ? `No indexed documents matched "${searchQuery}". Try a different keyword or reset filters.`
                  : 'Only fully parsed & indexed documents appear here. Upload a PDF from your PC to get started.'}
              </p>
              {!searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    if (localFileInputRef.current) {
                      localFileInputRef.current.click();
                    } else {
                      onClose();
                      onOpenUploadFromPC();
                    }
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] text-xs font-semibold transition-all active:scale-95 cursor-pointer flex items-center gap-1.5"
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload Document from PC</span>
                </button>
              )}
            </div>
          ) : (
            <>
              {optimisticUploads.map((opt) => (
                <div
                  key={opt.id}
                  className="p-3 rounded-xl border border-[#292929] bg-[#111111] flex items-center justify-between gap-3 text-[#A3A3A3]"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center shrink-0">
                      <Loader2 className="w-4 h-4 animate-spin text-[#FFFFFF]" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[#FFFFFF] truncate">{opt.name}</p>
                      <p className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">Uploading & parsing document...</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-[#A3A3A3] shrink-0">Processing</span>
                </div>
              ))}
              {filteredItems.map((item) => {
              const isAttached = attachedSet.has(item.name.toLowerCase());
              const isDeleting = deletingName === item.name;

              return (
                <div
                  key={item.id}
                  className={`relative p-3 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                    isAttached
                      ? 'bg-[#171717] border-[#FFFFFF]/30 text-[#FFFFFF]'
                      : 'bg-[#111111] hover:bg-[#171717] border-[#292929] hover:border-[#292929] text-[#A3A3A3] hover:text-[#FFFFFF]'
                  }`}
                  title={item.name}
                >
                  {/* Left: Icon & Info */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="relative shrink-0">
                      <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF]">
                        <FileText className="w-4 h-4 text-[#FFFFFF]" />
                      </div>
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-semibold text-[#FFFFFF] truncate">
                          {item.name}
                        </h4>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-[#A3A3A3] mt-0.5">
                        <span className="font-mono">{item.size}</span>
                        {item.pages && (
                          <>
                            <span>•</span>
                            <span>{item.pages} pp.</span>
                          </>
                        )}
                        <span>•</span>
                        <span className="inline-flex items-center gap-1 text-[#FFFFFF] font-mono text-[10px]">
                          <span className="w-1 h-1 rounded-full bg-[#FFFFFF]" />
                          <span>Ready</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right Actions */}
                  <div className="shrink-0 flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDocumentInNewTab(item);
                      }}
                      className="p-1.5 text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] rounded-lg border border-transparent hover:border-[#292929] transition-all cursor-pointer flex items-center justify-center shrink-0"
                      title={`Open "${item.name}" in new tab`}
                      aria-label={`Open ${item.name} in new tab`}
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-[#A3A3A3]" />
                    </button>

                    <button
                      type="button"
                      onClick={() => onSelectDocument(item)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer ${
                        isAttached
                          ? 'bg-[#171717] border border-[#292929] text-[#FFFFFF]'
                          : 'bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000]'
                      }`}
                    >
                      {isAttached ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-[#FFFFFF]" />
                          <span>Attached</span>
                        </>
                      ) : (
                        <>
                          <Plus className="w-3.5 h-3.5 text-[#000000]" />
                          <span>Attach</span>
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      disabled={isDeleting}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteDocument(item.name);
                      }}
                      className="p-1.5 text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] rounded-lg transition-all cursor-pointer disabled:opacity-50"
                      title={`Delete "${item.name}" from library`}
                      aria-label={`Delete ${item.name}`}
                    >
                      {isDeleting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#FFFFFF]" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5 text-[#A3A3A3]" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="h-14 px-5 sm:px-6 border-t border-[#292929] bg-[#0A0A0A] flex items-center justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] text-xs font-semibold transition-all active:scale-95 cursor-pointer shadow-sm"
          >
            Done
          </button>
        </div>
      </div>

      {/* Parsed Extracted Markdown & OKF Catalog Modal */}
      <ExtractedDocumentModal
        isOpen={artifactModal.isOpen}
        onClose={() => setArtifactModal((prev) => ({ ...prev, isOpen: false }))}
        documentName={artifactModal.documentName}
        type={artifactModal.type}
        url={artifactModal.url}
      />
    </div>
  );
};
