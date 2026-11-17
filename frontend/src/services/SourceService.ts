import { type ApiResponse, apiClient } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { getApiBaseUrl } from '../app/config';
import {
  type DeleteDocumentResponse,
  DeleteDocumentResponseSchema,
  type DocumentListResponse,
  DocumentListResponseSchema,
  type DocumentStatusResponse,
  DocumentStatusResponseSchema,
  type UploadResponse,
  UploadResponseSchema,
} from '../types';

export class SourceService {
  /**
   * Authoritative list of active confirmed ready documents
   */
  public async getDocuments(signal?: AbortSignal): Promise<ApiResponse<DocumentListResponse>> {
    return apiClient.request<DocumentListResponse>(
      ENDPOINTS.DOCUMENTS,
      DocumentListResponseSchema,
      {
        method: 'GET',
        signal,
      }
    );
  }

  /**
   * Synchronous Document upload (PDF, TXT, DOCX, MD, CSV)
   * Enforces IBM Docling parser at 100% potential for layout & table fidelity
   * Tries POST /api/upload first; falls back to /api/upload-academic-pdfs
   * 120s timeout configured for large files
   */
  public async uploadPdfs(
    files: File[],
    signal?: AbortSignal,
    options?: { parseMode?: 'fast' | 'expert'; parser?: string; sessionId?: string }
  ): Promise<ApiResponse<UploadResponse>> {
    if (typeof window !== 'undefined') {
      (window as any).__RAISE_ACTIVE_OPS__ = ((window as any).__RAISE_ACTIVE_OPS__ || 0) + 1;
    }
    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append('files', file);
      }
      if (options?.sessionId) {
        formData.append('session_id', options.sessionId);
      }

      // Pass parser and mode parameters based on selected mode
      const mode = options?.parseMode || 'fast';
      const isExpert = mode === 'expert' || options?.parser === 'docling';
      const parser = options?.parser || (isExpert ? 'docling' : 'fast');
      formData.append('parser', parser);
      formData.append('engine', parser);
      formData.append('parse_mode', mode);
      formData.append('mode', mode);
      if (isExpert) {
        formData.append('extract_tables', 'true');
        formData.append('full_potential', 'true');
      }

      // 1. Try standard POST /api/upload with query parameters
      const uploadUrl = isExpert
        ? `${ENDPOINTS.UPLOAD}?parser=docling&mode=expert`
        : ENDPOINTS.UPLOAD;

      const uploadRes = await apiClient.request<any>(uploadUrl, undefined, {
        method: 'POST',
        body: formData,
        signal,
        timeoutMs: 120000,
      });

      if (uploadRes.status === 200 && uploadRes.data) {
        const data = uploadRes.data;
        const parsedDirect = UploadResponseSchema.safeParse(data);
        if (parsedDirect.success) {
          return {
            data: parsedDirect.data,
            error: null,
            isMock: uploadRes.isMock,
            status: 200,
          };
        }

        const synthesized: UploadResponse = {
          status: data.status || 'success',
          uploaded_count: data.uploaded_count ?? files.length,
          reports: Array.isArray(data.reports)
            ? data.reports
            : files.map((f) => ({
                filename: f.name,
                pages_processed: 1,
                chunks_extracted: data.total_chunks ?? 1,
                facts_extracted: data.total_entities ?? 0,
                triples_extracted: 0,
              })),
          total_nodes: data.total_nodes ?? data.total_entities ?? 0,
          total_edges: data.total_edges ?? 0,
        };
        const parsedSynth = UploadResponseSchema.safeParse(synthesized);
        return {
          data: parsedSynth.success ? parsedSynth.data : synthesized,
          error: null,
          isMock: uploadRes.isMock,
          status: 200,
        };
      }

      // 2. Fallback to /api/upload-academic-pdfs with Docling query parameters
      const fallbackUrl = isExpert
        ? `${ENDPOINTS.UPLOAD_ACADEMIC_PDFS}?parser=docling&mode=expert`
        : ENDPOINTS.UPLOAD_ACADEMIC_PDFS;

      return await apiClient.request<UploadResponse>(fallbackUrl, UploadResponseSchema, {
        method: 'POST',
        body: formData,
        signal,
        timeoutMs: 120000,
      });
    } finally {
      if (typeof window !== 'undefined') {
        (window as any).__RAISE_ACTIVE_OPS__ = Math.max(
          0,
          ((window as any).__RAISE_ACTIVE_OPS__ || 1) - 1
        );
      }
    }
  }

  /**
   * Prunes document from knowledge vault
   * Tries DELETE /api/documents/{id} first; falls back to POST /api/documents/delete
   */
  public async deleteDocument(
    filenameOrId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<DeleteDocumentResponse>> {
    const cleanId = filenameOrId.trim();

    // 1. Try DELETE /api/documents/{id}
    const deleteRes = await apiClient.request<any>(
      ENDPOINTS.DELETE_DOCUMENT_BY_ID(cleanId),
      undefined,
      {
        method: 'DELETE',
        signal,
      }
    );

    if (deleteRes.status >= 200 && deleteRes.status < 300) {
      return {
        data: {
          status: 'success',
          filename: cleanId,
          documents: [],
          total_count: 0,
        },
        error: null,
        isMock: deleteRes.isMock,
        status: deleteRes.status,
      };
    }

    // If backend explicitly forbade deletion (e.g. 403 Forbidden for protected document), do NOT fall back
    if (deleteRes.status === 403) {
      return deleteRes;
    }

    // 2. Fallback to POST /api/documents/delete
    return apiClient.request<DeleteDocumentResponse>(
      ENDPOINTS.DELETE_DOCUMENT,
      DeleteDocumentResponseSchema,
      {
        method: 'POST',
        body: JSON.stringify({ filename: cleanId, id: cleanId }),
        signal,
      }
    );
  }

  /**
   * Deep-linked PDF URL with page fragment anchor
   */
  public getPdfUrl(filename: string, pageNumber?: number): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const cleanFilename = encodeURIComponent(filename);
    const pageFragment = pageNumber && pageNumber > 0 ? `#page=${pageNumber}` : '';
    return `${base}/api/pdf/${cleanFilename}${pageFragment}`;
  }

  /**
   * High-speed direct PDF URL opened in browser default viewer
   */
  public getViewerUrl(filename: string, pageNumber: number = 1, _excerpt?: string): string {
    return this.getPdfUrl(filename, pageNumber);
  }

  /**
   * High-speed URL that streams ONLY the single referenced page (<100KB)
   * in ~25ms instead of downloading the entire multi-megabyte PDF.
   */
  public getSinglePagePdfUrl(filename: string, pageNumber: number): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const cleanFilename = encodeURIComponent(filename);
    const safePage = Math.max(1, pageNumber || 1);
    return `${base}/api/pdf/${cleanFilename}/pages/${safePage}/pdf`;
  }

  /**
   * High-DPI PNG image URL of the single page (150 DPI)
   */
  public getSinglePageImageUrl(filename: string, pageNumber: number): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const cleanFilename = encodeURIComponent(filename);
    const safePage = Math.max(1, pageNumber || 1);
    return `${base}/api/pdf/${cleanFilename}/pages/${safePage}/image`;
  }

  /**
   * Standalone HTML reader view of the single page
   */
  public getSinglePageViewUrl(filename: string, pageNumber: number): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const cleanFilename = encodeURIComponent(filename);
    const safePage = Math.max(1, pageNumber || 1);
    return `${base}/api/pdf/${cleanFilename}/pages/${safePage}/view`;
  }

  /**
   * Loads default research vault documents
   */
  public async loadVaultDefaults(signal?: AbortSignal): Promise<ApiResponse<any>> {
    return apiClient.request(ENDPOINTS.LOAD_VAULT_DEFAULTS, undefined, {
      method: 'POST',
      signal,
    });
  }

  /**
   * Polls real-time ingestion progress for a document.
   * Backend: GET /api/documents/{id}/status
   * Returns phase, percent, and optional detail string.
   */
  public async getDocumentStatus(
    docId: string,
    signal?: AbortSignal
  ): Promise<ApiResponse<DocumentStatusResponse>> {
    return apiClient.request<DocumentStatusResponse>(
      ENDPOINTS.DOCUMENT_STATUS(docId),
      DocumentStatusResponseSchema,
      {
        method: 'GET',
        signal,
      }
    );
  }

  /**
   * Real-time Document Ingestion Stream: GET /api/documents/{doc_id}/events
   * Emits milestone progress (uploading -> parsing -> chunking -> embedding -> ready)
   * Automatically closes on [DONE] or terminal status.
   */
  public watchDocumentIngestionEvents(
    docId: string,
    onProgress: (status: DocumentStatusResponse) => void,
    onComplete?: () => void,
    onError?: (err: any) => void
  ): () => void {
    const base = getApiBaseUrl();
    const sseUrl = `${base}${ENDPOINTS.DOCUMENT_EVENTS(docId)}`;
    let closed = false;

    if (typeof window !== 'undefined' && 'EventSource' in window) {
      try {
        const es = new EventSource(sseUrl);

        es.onmessage = (event) => {
          if (closed) return;
          if (event.data === '[DONE]') {
            es.close();
            closed = true;
            onProgress({
              phase: 'ready',
              percent: 100,
              status: 'ready',
              detail: 'Document ingestion complete and graph synchronized',
            });
            onComplete?.();
            return;
          }

          try {
            const rawJson = JSON.parse(event.data);
            const parsed = DocumentStatusResponseSchema.safeParse(rawJson);
            if (parsed.success) {
              const statusData = parsed.data;
              onProgress(statusData);
              if (
                statusData.status === 'ready' ||
                statusData.percent >= 100 ||
                statusData.phase === 'ready'
              ) {
                es.close();
                closed = true;
                onComplete?.();
              }
            } else {
              const data =
                rawJson && typeof rawJson === 'object' ? (rawJson as Record<string, any>) : {};
              onProgress({
                phase: (data.phase as any) || 'processing',
                percent: typeof data.percent === 'number' ? data.percent : 50,
                status: data.status || (data.percent >= 100 ? 'ready' : 'processing'),
                detail: data.detail || '',
              });
              if (
                data.status === 'ready' ||
                (typeof data.percent === 'number' && data.percent >= 100)
              ) {
                es.close();
                closed = true;
                onComplete?.();
              }
            }
          } catch {}
        };

        es.onerror = (err) => {
          es.close();
          if (!closed) {
            onError?.(err);
          }
        };

        return () => {
          closed = true;
          es.close();
        };
      } catch (err) {
        onError?.(err);
      }
    }

    return () => {
      closed = true;
    };
  }

  /**
   * Triggers instant disk scan to discover any PDFs dropped into data/documents/
   */
  public async scanDocuments(signal?: AbortSignal): Promise<ApiResponse<DocumentListResponse>> {
    return apiClient.request<DocumentListResponse>(
      ENDPOINTS.DOCUMENTS_SCAN,
      undefined,
      {
        method: 'POST',
        signal,
      }
    );
  }

  /**
   * Resolved URL for Parsed Extracted Markdown
   */
  public getExtractedMarkdownUrl(filename: string): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    return `${base}${ENDPOINTS.DOCUMENT_EXTRACTED_MD(filename)}`;
  }

  /**
   * Resolved URL for OKF Catalog
   */
  public getOkfCatalogUrl(filename: string): string {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    return `${base}${ENDPOINTS.DOCUMENT_OKF_CATALOG(filename)}`;
  }

  /**
   * Fetches raw extracted markdown content for a document
   * Seamlessly tries both /extracted-markdown and /markdown endpoints
   */
  public async fetchExtractedMarkdown(
    filenameOrUrl: string,
    signal?: AbortSignal
  ): Promise<string> {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const cleanDoc = filenameOrUrl
      .replace(/^https?:\/\/[^/]+/i, '')
      .replace(/^\/api\/documents\//i, '')
      .replace(/\/(extracted-markdown|markdown)$/i, '');

    const candidates = [
      filenameOrUrl.startsWith('http://') || filenameOrUrl.startsWith('https://')
        ? filenameOrUrl
        : filenameOrUrl.startsWith('/')
          ? `${base}${filenameOrUrl}`
          : `${base}${ENDPOINTS.DOCUMENT_EXTRACTED_MD(filenameOrUrl)}`,
      `${base}/api/documents/${encodeURIComponent(cleanDoc)}/extracted-markdown`,
      `${base}/api/documents/${encodeURIComponent(cleanDoc)}/markdown`,
    ];

    const uniqueUrls = Array.from(new Set(candidates));
    let lastError: Error | null = null;

    for (const u of uniqueUrls) {
      try {
        const resp = await fetch(u, { method: 'GET', signal });
        if (resp.ok) {
          return await resp.text();
        }
        lastError = new Error(`Failed to load extracted markdown: ${resp.status} ${resp.statusText}`);
      } catch (err: any) {
        lastError = err;
      }
    }

    throw lastError || new Error('Failed to load extracted markdown');
  }

  /**
   * Fetches OKF catalog for a document (returns parsed JSON or raw markdown text)
   */
  public async fetchOkfCatalog(
    filenameOrUrl: string,
    signal?: AbortSignal
  ): Promise<{ text: string; data?: any }> {
    const base = getApiBaseUrl().replace(/\/+$/, '');
    const rawUrl =
      filenameOrUrl.startsWith('http://') || filenameOrUrl.startsWith('https://')
        ? filenameOrUrl
        : filenameOrUrl.startsWith('/')
          ? `${base}${filenameOrUrl}`
          : `${base}${ENDPOINTS.DOCUMENT_OKF_CATALOG(filenameOrUrl)}`;

    const urlWithJson = rawUrl.includes('?') ? `${rawUrl}&format=json` : `${rawUrl}?format=json`;

    try {
      const resp = await fetch(urlWithJson, { method: 'GET', signal });
      if (resp.ok) {
        const contentType = resp.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          const json = await resp.json();
          return { text: JSON.stringify(json, null, 2), data: json };
        }
        const text = await resp.text();
        return { text };
      }
    } catch {
      // fallback to raw URL
    }

    const fallbackResp = await fetch(rawUrl, { method: 'GET', signal });
    if (!fallbackResp.ok) {
      throw new Error(`Failed to load OKF catalog: ${fallbackResp.status} ${fallbackResp.statusText}`);
    }
    const text = await fallbackResp.text();
    return { text };
  }
}

export const sourceService = new SourceService();
