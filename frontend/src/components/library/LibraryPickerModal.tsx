import { useQuery, useQueryClient } from '@tanstack/react-query';
import type React from 'react';
import { useCallback, useMemo, useRef, useState } from 'react';
import { documentsQueryOptions } from '../../api/queryOptions';
import { useEscapeKey, useScrollLock } from '../../hooks';
import { useDocumentViewerStore } from '../../stores/useDocumentViewerStore';
import { documentItemToLibraryItem, type LibraryItem } from '../settings/SettingsLibraryTab';
import { sourceService } from '../../services/SourceService';
import { CircularUploadProgress } from '../ui/CircularUploadProgress';
import { ExtractedDocumentModal } from './ExtractedDocumentModal';
import { getDocumentStageLabel } from '../../utils/documentStageUtils';

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
}

export const LibraryPickerModal: React.FC<LibraryPickerModalProps> = ({
  isOpen,
  onClose,
  onSelectDocument,
  attachedDocNames,
  onOpenUploadFromPC,
  onViewPdf,
  onAttachAll,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'pdf' | 'csv' | 'docx' | 'other'>('all');
  const [optimisticUploads, setOptimisticUploads] = useState<OptimisticUploadItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
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

  // TanStack Query v5 declarative caching & data fetching
  const { data: rawDocuments = [], isLoading } = useQuery({
    ...documentsQueryOptions(),
    enabled: isOpen,
    placeholderData: (prev) => prev,
  });

  // Fast preview hash generation using Web Crypto SHA-256 slice or metadata
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

  // Format local file size cleanly (e.g. "2.4 MB" or "840 KB")
  const formatFileSize = (bytes: number): string => {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    if (bytes >= 1024) {
      return `${Math.round(bytes / 1024)} KB`;
    }
    return `${bytes} B`;
  };

  // Immediate optimistic upload handler
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

      // Progress tick animation
      const interval = setInterval(() => {
        setOptimisticUploads((prev) =>
          prev.map((item) => {
            if (newOptimistic.some((n) => n.id === item.id) && item.progress < 85) {
              return { ...item, progress: Math.min(85, item.progress + 14) };
            }
            return item;
          })
        );
      }, 400);

      try {
        const uploadRes = await sourceService.uploadPdfs(files, undefined, {
          parseMode: 'fast',
          parser: 'fast',
        });
        if (uploadRes.error || !uploadRes.data) {
          throw new Error(uploadRes.error?.message || 'Upload failed');
        }

        clearInterval(interval);
        setOptimisticUploads((prev) =>
          prev.map((item) =>
            newOptimistic.some((n) => n.id === item.id)
              ? { ...item, progress: 100, status: 'ready' }
              : item
          )
        );

        // Auto-attach each uploaded document to the drawer
        for (const file of files) {
          onSelectDocument({
            id: `doc-${file.name}`,
            name: file.name,
            size: formatFileSize(file.size),
            bytes: file.size,
            uploadedAt: 'Just now',
            timestamp: Date.now(),
            type: (file.name.split('.').pop()?.toLowerCase() || 'pdf') as any,
            pages: 1,
            chunks: 1,
            status: 'ready',
            color: 'indigo',
          });
        }

        await queryClient.invalidateQueries({ queryKey: ['documents'] });
        setTimeout(() => {
          setOptimisticUploads((prev) =>
            prev.filter((item) => !newOptimistic.some((n) => n.id === item.id))
          );
        }, 1800);
      } catch {
        clearInterval(interval);
        setOptimisticUploads((prev) =>
          prev.map((item) =>
            newOptimistic.some((n) => n.id === item.id)
              ? { ...item, status: 'error', progress: 0 }
              : item
          )
        );
        setTimeout(() => {
          setOptimisticUploads((prev) =>
            prev.filter((item) => !newOptimistic.some((n) => n.id === item.id))
          );
        }, 5000);
      }
    },
    [computePreviewHash, queryClient, onSelectDocument]
  );

  const items = useMemo(() => {
    const backendItems = rawDocuments.map(documentItemToLibraryItem);
    const backendNames = new Set(backendItems.map((b) => b.name.toLowerCase()));

    // Filter out optimistic items that have already completed and appeared in backend
    const pendingOptimistic: (LibraryItem & { previewHash?: string })[] = optimisticUploads
      .filter((opt) => !backendNames.has(opt.name.toLowerCase()))
      .map((opt) => ({
        id: opt.id,
        name: opt.name,
        size: opt.size,
        bytes: opt.bytes,
        uploadedAt: opt.status === 'error' ? 'Failed (Gateway Offline)' : 'Processing...',
        timestamp: opt.timestamp,
        type: (opt.name.split('.').pop()?.toLowerCase() || 'pdf') as any,
        pages: 1,
        chunks: 0,
        status: opt.status === 'ready' ? 'ready' : opt.status === 'error' ? 'error' : 'processing',
        color: opt.status === 'error' ? ('rose' as const) : ('indigo' as const),
        uploadProgress: opt.status === 'error' ? 0 : opt.progress,
        previewHash: opt.previewHash,
      }));

    return [...pendingOptimistic, ...backendItems];
  }, [rawDocuments, optimisticUploads]);

  const apiReadyFilenames = useMemo(() => {
    return new Set(
      rawDocuments
        .filter((d) => d.status === 'ready' || d.status === 'indexed')
        .map((d) => (d.filename || d.name || '').toLowerCase())
        .filter(Boolean)
    );
  }, [rawDocuments]);

  // React hook replacing window keydown ESC listener (only when child modal is not open)
  useEscapeKey(onClose, isOpen && !artifactModal.isOpen);

  const isItemIndexed = (item: LibraryItem): boolean => {
    if (item.status === 'processing') return false;
    if (item.uploadProgress !== undefined && item.uploadProgress < 100) return false;
    if (apiReadyFilenames.size > 0 && apiReadyFilenames.has(item.name.toLowerCase())) {
      return true;
    }
    return item.status === 'indexed' || item.status === 'ready';
  };

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

  const unattachedReadyItems = filteredItems.filter(
    (item) => isItemIndexed(item) && !attachedSet.has(item.name.toLowerCase().trim())
  );

  useScrollLock(isOpen);

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 z-[120] flex items-center justify-center p-[clamp(0.5rem,2vw,1.25rem)] bg-black/60 backdrop-blur-sm animate-in fade-in duration-150 select-none ${
        isDragOver ? 'ring-4 ring-indigo-500/60' : ''
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
        className="w-[min(94vw,38rem)] max-h-[88dvh] bg-white dark:bg-[#1e1f20] text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="library-picker-title"
      >
        {/* Header */}
        <div className="px-[clamp(0.875rem,2vw,1.25rem)] py-[clamp(0.75rem,1.8vw,1rem)] border-b border-slate-200 dark:border-white/10 flex items-center justify-between bg-slate-50/80 dark:bg-white/[0.02]">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl bg-indigo-50 dark:bg-indigo-500/15 border border-indigo-200/60 dark:border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-[#a8c7fa] shrink-0">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
            </div>
            <div className="min-w-0">
              <h3
                id="library-picker-title"
                className="text-sm font-semibold text-slate-900 dark:text-white truncate"
              >
                Attach from Knowledge Base Library
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-[#a8a8a8] truncate">
                Pre-indexed library documents — ready for instant research
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-200/50 dark:hover:bg-white/10 transition-colors cursor-pointer"
            aria-label="Close"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search & Filter Bar */}
        <div className="p-4 border-b border-slate-200/80 dark:border-white/5 space-y-2.5 bg-slate-50/40 dark:bg-white/[0.01]">
          <div className="relative">
            <svg
              className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <circle cx="11" cy="11" r="8" />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-4.35-4.35"
              />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search library documents..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl bg-white dark:bg-[#18191a] border border-slate-200 dark:border-white/10 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Type Filter Pills & Attach All */}
          <div className="flex items-center justify-between gap-1.5 overflow-x-auto pb-0.5">
            <div className="flex items-center gap-1.5">
              {(['all', 'pdf', 'csv', 'docx', 'other'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTypeFilter(t)}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors whitespace-nowrap cursor-pointer ${
                    typeFilter === t
                      ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                      : 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-[#c4c7c5] hover:bg-slate-200/70 dark:hover:bg-white/10'
                  }`}
                >
                  {t === 'all' ? 'All' : t.toUpperCase()}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => {
                  if (localFileInputRef.current) {
                    localFileInputRef.current.click();
                  } else {
                    onOpenUploadFromPC();
                  }
                }}
                className="text-[11px] font-semibold px-2.5 py-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100 transition-all cursor-pointer whitespace-nowrap shrink-0 flex items-center gap-1 shadow-2xs active:scale-95"
                title="Add new document from PC to library"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
                </svg>
                <span>Add Document</span>
              </button>

              {onAttachAll && unattachedReadyItems.length > 0 && (
                <button
                  type="button"
                  onClick={() => onAttachAll(unattachedReadyItems)}
                  className="text-[11px] font-semibold px-2.5 py-1 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white transition-all cursor-pointer whitespace-nowrap shrink-0 shadow-2xs"
                  title={`Attach all ${unattachedReadyItems.length} ready documents to current chat`}
                >
                  Attach All ({unattachedReadyItems.length})
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Documents List */}
        <div
          className="flex-1 overflow-y-auto p-4 space-y-2.5 max-h-[50vh]"
          style={{ scrollbarWidth: 'thin' }}
        >
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-xs text-slate-400 dark:text-slate-500 gap-2.5">
              <div className="w-6 h-6 rounded-full border-2 border-slate-300 dark:border-slate-600 border-t-indigo-600 animate-spin" />
              <span className="font-medium">Checking Knowledge Base Library...</span>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-white/5 border border-slate-200/80 dark:border-white/10 flex items-center justify-center text-slate-400 dark:text-slate-500 mb-3">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.5"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              </div>
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 mb-1">
                {searchQuery ? 'No matching documents found' : 'Your Library is currently empty'}
              </p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-xs mb-4">
                {searchQuery
                  ? `No indexed documents matched "${searchQuery}". Try a different keyword or reset filters.`
                  : 'No documents in library yet. Upload files from your PC to get started.'}
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
                  className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium transition-all active:scale-95 cursor-pointer shadow-xs flex items-center gap-1.5"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Upload Document from PC</span>
                </button>
              )}
            </div>
          ) : (
            filteredItems.map((item) => {
              const indexed = isItemIndexed(item);
              const isAttached = attachedSet.has(item.name.toLowerCase());
              const progress = item.uploadProgress ?? 45;

              const badgeBg =
                item.color === 'rose'
                  ? 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400 border-rose-200/60 dark:border-rose-500/20'
                  : item.color === 'emerald'
                    ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400 border-emerald-200/60 dark:border-emerald-500/20'
                    : item.color === 'amber'
                      ? 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400 border-amber-200/60 dark:border-amber-500/20'
                      : 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-400 border-indigo-200/60 dark:border-indigo-500/20';

              return (
                <div
                  key={item.id}
                  className={`relative p-3 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                    !indexed
                      ? item.status === 'error'
                        ? 'bg-rose-50/60 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20'
                        : 'bg-amber-50/60 dark:bg-amber-500/10 border-amber-300 dark:border-amber-500/30 shadow-2xs cursor-wait'
                      : isAttached
                        ? 'bg-indigo-50/40 dark:bg-indigo-500/10 border-indigo-300/80 dark:border-indigo-500/30'
                        : 'bg-slate-50/70 dark:bg-white/[0.03] border-slate-200/80 dark:border-white/10 hover:border-indigo-300 dark:hover:border-indigo-500/40 hover:bg-white dark:hover:bg-[#252834]'
                  }`}
                  title={
                    !indexed
                      ? `Document is still processing... (${Math.round(progress)}%)`
                      : item.name
                  }
                >
                  {/* Left: Icon & Info */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="relative shrink-0">
                      <div className={`p-2 rounded-xl border ${badgeBg}`}>
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                          />
                        </svg>
                      </div>
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                          {item.name}
                        </h4>
                        {!indexed && (
                          item.status === 'error' ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 shrink-0 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                              <span>Gateway Offline</span>
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 shrink-0 flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full border border-amber-500 border-t-transparent animate-spin" />
                              <span>{getDocumentStageLabel(progress)}</span>
                            </span>
                          )
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-[#a8a8a8] mt-0.5">
                        <span className="font-mono">{item.size}</span>
                        {(item as any).previewHash && (
                          <>
                            <span>•</span>
                            <span
                              className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-500/20"
                              title={`Optimistic Local Hash: ${(item as any).previewHash}`}
                            >
                              #{(item as any).previewHash}
                            </span>
                          </>
                        )}
                        {item.pages && (
                          <>
                            <span>•</span>
                            <span>{item.pages} pp.</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Exactly ONE Circular Progress Spinner */}
                  <div className="shrink-0">
                    {!indexed ? (
                      item.status === 'error' ? (
                        <span className="text-[11px] font-mono font-semibold text-rose-500 px-2 py-1">
                          Failed
                        </span>
                      ) : (
                        <div
                          className="flex items-center gap-1 text-[11px] font-mono text-indigo-600 dark:text-[#a8c7fa] px-2 py-1"
                          title={`Parsing progress: ${Math.round(progress)}%`}
                        >
                          <CircularUploadProgress
                            progress={progress}
                            size={24}
                            strokeWidth={2.5}
                            showPercentText={true}
                          />
                        </div>
                      )
                    ) : (
                      <div className="flex items-center gap-1.5">
                        {item.type === 'pdf' && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              useDocumentViewerStore.getState().openDocument(item.name, 1);
                              onViewPdf?.(item.name, 1);
                            }}
                            className="px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-[#a8c7fa] hover:bg-slate-100 dark:hover:bg-white/10 transition-colors flex items-center gap-1 cursor-pointer"
                            title={`Open ${item.name} in new tab`}
                          >
                            <svg
                              className="w-3.5 h-3.5"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                              />
                            </svg>
                            <span className="hidden sm:inline">Preview</span>
                          </button>
                        )}


                        <button
                          type="button"
                          onClick={() => onSelectDocument(item)}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                            isAttached
                              ? 'bg-emerald-600 text-white shadow-xs'
                              : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white shadow-xs'
                          }`}
                        >
                          {isAttached ? (
                            <>
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                viewBox="0 0 24 24"
                              >
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                              <span>Attached</span>
                            </>
                          ) : (
                            <>
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M12 4v16m8-8H4"
                                />
                              </svg>
                              <span>Attach</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 border-t border-slate-200 dark:border-white/10 bg-slate-50/80 dark:bg-white/[0.02] flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100 text-xs font-medium transition-all active:scale-95 cursor-pointer shadow-xs"
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
