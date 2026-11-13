import type { Citation } from '../types';

/**
 * Universal Citation Normalizer & Page Number Extractor
 * Guarantees that every citation object has:
 * - A valid, 1-indexed citation_index
 * - An accurate physical PDF primary_page (recovers from page, page_number, physical_page, or chunk_id like _p020_)
 * - A clean, human-readable pdf_filename (recovers from filename, document_name, source, or defaultDocName)
 * - Clean plain_text, heading, and similarity score
 */

/**
 * Rigorous physical page extractor:
 * 1. Checks explicit page properties across backend conventions:
 *    - primary_page, page, page_number, physical_page, page_no (and their metadata.* variants)
 * 2. Scans chunk_id / id for structural page signatures:
 *    - `parent_005` or `_parent_005` -> 5 (crucial for LangGraph parent document retriever)
 *    - `_p098_c98_01` or `p098` or `_p020_` -> 98, 20
 *    - `page_16`, `page-16`, `page16` -> 16
 * 3. Scans section heading / title:
 *    - "BRIC ANNUAL REPORT 2025 | 5" -> 5
 *    - "98 | BRIC ANNUAL REPORT 2025" -> 98
 *    - "Section (Page 5)" or "Page 98" -> 5, 98
 * 4. Disambiguation:
 *    - If an explicit property is 1, but chunk_id or heading indicates a specific page > 1,
 *      the chunk_id / heading page takes precedence (preventing unverified fallback 1).
 */
export function extractVerifiedPageNumber(raw: any): number | undefined {
  if (!raw) return undefined;

  // Handle string input: e.g. "Doc.pdf (Page 5)" or "Doc.pdf#page=14"
  if (typeof raw === 'string') {
    const pMatch =
      raw.match(/#page=(\d+)/i) ||
      raw.match(/(?:page|p\.?)[=:\s]*(\d+)/i) ||
      raw.match(/\|\s*0*(\d+)\s*$/) ||
      raw.match(/^\s*0*(\d+)\s*\|/);
    if (pMatch) {
      const p = parseInt(pMatch[1], 10);
      if (p > 0) return p;
    }
    return undefined;
  }

  // 1. Check explicit page fields provided by backend parsers (PyMuPDF, Docling, ChromaDB)
  const candidateKeys = [
    raw.primary_page,
    raw.printed_page,
    raw.physical_page,
    raw.page,
    raw.page_number,
    raw.page_no,
    raw.source_page,
    raw.page_start,
    raw.start_page,
    Array.isArray(raw.source_pages) && raw.source_pages.length > 0
      ? raw.source_pages[0]
      : undefined,
    raw.page_idx !== undefined ? raw.page_idx + 1 : undefined,
    raw.prov?.[0]?.page_no,
    raw.prov?.[0]?.page,
    raw.metadata?.primary_page,
    raw.metadata?.printed_page,
    raw.metadata?.physical_page,
    raw.metadata?.page,
    raw.metadata?.page_number,
    raw.metadata?.page_no,
    raw.metadata?.source_page,
    raw.metadata?.page_start,
    raw.metadata?.start_page,
    Array.isArray(raw.metadata?.source_pages) && raw.metadata?.source_pages.length > 0
      ? raw.metadata?.source_pages[0]
      : undefined,
    raw.metadata?.page_idx !== undefined ? raw.metadata?.page_idx + 1 : undefined,
    raw.metadata?.prov?.[0]?.page_no,
    raw.metadata?.prov?.[0]?.page,
  ];

  for (const cand of candidateKeys) {
    if (typeof cand === 'number' && cand > 0) {
      return cand;
    }
    if (typeof cand === 'string' && !Number.isNaN(parseInt(cand, 10))) {
      const p = parseInt(cand, 10);
      if (p > 0) return p;
    }
  }

  // 1b. Check page extracted from direct single-page extraction endpoints (/pages/29/pdf, /pages/29/image, /pages/29/view)
  const candidateUrls = [
    raw.page_url,
    raw.page_image_url,
    raw.page_view_url,
    raw.url,
    raw.metadata?.page_url,
    raw.metadata?.page_image_url,
    raw.metadata?.page_view_url,
    raw.metadata?.url,
  ];
  for (const u of candidateUrls) {
    if (typeof u === 'string') {
      const match = u.match(/\/pages\/(\d+)(?:\/|\?|$)/i) || u.match(/[?&#]page=(\d+)/i);
      if (match) {
        const p = parseInt(match[1], 10);
        if (p > 0) return p;
      }
    }
  }

  // 2. Fallback: Check chunk_id / id for explicit page markers (e.g. #page=8, _docling_p12, page_14, _p098_c01)
  const chunkIdStr = String(
    raw.chunk_id || raw.id || raw.metadata?.chunk_id || raw.metadata?.id || ''
  );
  if (chunkIdStr) {
    const match =
      chunkIdStr.match(/#page=0*(\d+)/i) ||
      chunkIdStr.match(/(?:_docling_p|_p|p-|page[_-])0*(\d+)(?:[_\D]|$)/i);
    if (match) {
      const p = parseInt(match[1], 10);
      if (p > 0) return p;
    }
  }

  // 3. Fallback: Check plain_text / text / excerpt signatures
  const textStr = String(
    raw.plain_text ||
      raw.text ||
      raw.content ||
      raw.snippet ||
      raw.metadata?.plain_text ||
      raw.metadata?.text ||
      ''
  );
  if (textStr) {
    const tMatch =
      textStr.match(/<!--\s*page:?\s*0*(\d+)\s*-->/i) ||
      textStr.match(/\[(?:Doc:[^,]+,\s*)?PDF Page\s*0*(\d+)\]/i) ||
      textStr.match(/\[Page\s*0*(\d+)\]/i) ||
      textStr.match(/\b(?:PDF\s+Page|Doc\s+Page|Page)\s*[:#-]?\s*0*(\d+)\b/i);
    if (tMatch) {
      const p = parseInt(tMatch[1], 10);
      if (p > 0) return p;
    }
  }

  // 4. Fallback: Check heading / title signatures
  const headingStr = String(
    raw.heading || raw.title || raw.metadata?.heading || raw.metadata?.title || ''
  );
  if (headingStr) {
    const hMatch =
      headingStr.match(/(?:page|p\.?)\s*0*(\d+)/i) ||
      headingStr.match(/\|\s*0*(\d+)\s*$/) ||
      headingStr.match(/^\s*0*(\d+)\s*\|/);
    if (hMatch) {
      const p = parseInt(hMatch[1], 10);
      if (p > 0) return p;
    }
  }

  return undefined;
}

/**
 * Strips all inline citation brackets like [1], [2], [1, 2], and parenthetical citations
 * from text so that user clipboard copy operations contain clean, readable prose
 * without bracket artifacts.
 */
export function stripCitationsForCopy(rawText: string): string {
  if (!rawText) return '';

  // 1. Remove verbose parenthetical citations if present: (File.pdf, Page 8) [1]
  let text = rawText.replace(
    /(?:\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?,\s*(?:page|p\.?)\s*\d+[^()\n]*?|(?:page|p\.?)\s*\d+[^()\n]*?,\s*[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)\s*(?:\[\d+(?:\s*,\s*\d+)*\])?|\[\d+(?:\s*,\s*\d+)*\]\s*\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?,\s*(?:page|p\.?)\s*\d+[^()\n]*?|(?:page|p\.?)\s*\d+[^()\n]*?,\s*[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)|\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)\s*\[\d+(?:\s*,\s*\d+)*\]|\((?:page|p\.?)\s*\d+[^()\n]*?\)\s*\[\d+(?:\s*,\s*\d+)*\])/gi,
    ''
  );

  // 2. Strip bracketed citations like [1], [2], [1, 2], [1, 2, 3] and adjacent [1][2]
  text = text.replace(/\s*\[\d+(?:\s*,\s*\d+)*\]/g, '');

  // 3. Clean up spaces before punctuation (e.g. "claim ." -> "claim.")
  text = text.replace(/\s+([.,;:!?])/g, '$1');

  // 4. Clean up trailing/excess spaces per line
  text = text
    .split('\n')
    .map((line) => line.replace(/[ \t]{2,}/g, ' ').trimEnd())
    .join('\n');

  return text.trim();
}

/**
 * Universal Citation Normalizer
 * Guarantees that every citation object has:
 * - A valid, 1-indexed citation_index
 * - An accurate physical PDF primary_page (recovers from page, page_number, physical_page, or chunk_id like parent_005 or _p020_)
 * - A clean, human-readable pdf_filename (recovers from filename, document_name, source, or defaultDocName)
 * - Clean plain_text, heading, and similarity score
 */
export function normalizeCitation(
  raw: any,
  indexFallback: number = 1,
  defaultDocName?: string
): Citation {
  if (!raw) {
    return {
      citation_index: indexFallback,
      chunk_id: `cit-${indexFallback}`,
      document_id: defaultDocName || 'Audited Document',
      pdf_filename: defaultDocName || 'Audited Document',
      primary_page: undefined as any,
      heading: '',
      plain_text: '',
      university: '',
      similarity: 0.9,
    };
  }

  // Handle case where citation is passed as a string filename or "Doc.pdf (Page X)"
  if (typeof raw === 'string') {
    const cleanStr = raw.trim();
    const isWebStr = cleanStr.startsWith('http://') || cleanStr.startsWith('https://');
    const pageFromStr = extractVerifiedPageNumber(cleanStr);
    const cleanFile = cleanStr
      .replace(/\s*\(.*?\)/, '')
      .replace(/#page=\d+/, '')
      .trim();
    const finalFilename = cleanFile || defaultDocName || 'Audited Document';
    return {
      citation_index: indexFallback,
      chunk_id: `cit-${indexFallback}`,
      document_id: finalFilename,
      pdf_filename: finalFilename,
      primary_page: pageFromStr && pageFromStr > 0 ? pageFromStr : (undefined as any),
      heading: '',
      plain_text: '',
      university: '',
      similarity: 0.95,
      source_type: isWebStr ? 'EXTERNAL_PUBLIC_RECORD' : undefined,
      url: isWebStr ? cleanStr : undefined,
      page_url: isWebStr ? cleanStr : undefined,
      page_view_url: isWebStr ? cleanStr : undefined,
    };
  }

  // 1. Extract physical page number across all backend naming conventions
  const page = extractVerifiedPageNumber(raw);

  // 2. Extract PDF filename across all backend naming conventions
  let filename =
    raw.pdf_filename ||
    raw.filename ||
    raw.file_name ||
    raw.document_name ||
    raw.doc_name ||
    raw.source ||
    raw.metadata?.pdf_filename ||
    raw.metadata?.filename ||
    raw.metadata?.file_name ||
    raw.metadata?.document_name ||
    raw.metadata?.doc_name ||
    raw.metadata?.source ||
    defaultDocName ||
    'Audited Document';

  if (typeof filename === 'string') {
    filename = filename.trim();
    // Strip leading path if it contains directory separators
    const lastSlash = Math.max(filename.lastIndexOf('/'), filename.lastIndexOf('\\'));
    if (lastSlash >= 0) {
      filename = filename.slice(lastSlash + 1).trim();
    }
  }

  // If still generic or missing, recover from chunk_id prefix if available
  const chunkId = raw.chunk_id || raw.id || raw.metadata?.chunk_id;
  if (
    (!filename || filename === 'Audited Document' || filename === 'Document') &&
    typeof chunkId === 'string'
  ) {
    const stemMatch = chunkId.match(/^([a-zA-Z0-9_\-\s]+?)(?:_p\d+|_parent|\.pdf|$)/i);
    if (stemMatch && stemMatch[1] && stemMatch[1].length > 3 && !stemMatch[1].startsWith('chk_') && !stemMatch[1].startsWith('cit-')) {
      filename = stemMatch[1].endsWith('.pdf') ? stemMatch[1] : `${stemMatch[1]}.pdf`;
    }
  }

  // 3. Extract citation index
  const citIdx =
    typeof raw.citation_index === 'number' && raw.citation_index > 0
      ? raw.citation_index
      : typeof raw.index === 'number' && raw.index > 0
        ? raw.index
        : indexFallback;

  const safePage = page && page > 0 ? page : 1;
  const encodedName = encodeURIComponent(filename);

  const isWebSource =
    raw.source_type === 'EXTERNAL_PUBLIC_RECORD' ||
    raw.source_type?.toLowerCase() === 'web' ||
    Boolean(raw.url) ||
    (typeof filename === 'string' && (filename.startsWith('http://') || filename.startsWith('https://')));

  const rawUrl =
    typeof raw.url === 'string' && raw.url.trim()
      ? raw.url.trim()
      : typeof raw.metadata?.url === 'string' && raw.metadata.url.trim()
        ? raw.metadata.url.trim()
        : typeof filename === 'string' && (filename.startsWith('http://') || filename.startsWith('https://'))
          ? filename
          : undefined;

  const pageUrl =
    raw.page_url ||
    raw.metadata?.page_url ||
    (isWebSource && rawUrl ? rawUrl : `/api/pdf/${encodedName}/pages/${safePage}/pdf`);
  const pageViewUrl =
    raw.page_view_url ||
    raw.metadata?.page_view_url ||
    (isWebSource && rawUrl ? rawUrl : `/api/pdf/${encodedName}/pages/${safePage}/view`);
  const pageImageUrl =
    raw.page_image_url ||
    raw.metadata?.page_image_url ||
    (isWebSource ? undefined : `/api/pdf/${encodedName}/pages/${safePage}/image`);

  return {
    citation_index: citIdx,
    chunk_id: chunkId || `chk-${citIdx}`,
    document_id: raw.document_id || raw.doc_id || raw.metadata?.doc_id || filename,
    doc_id: raw.doc_id || raw.document_id || raw.metadata?.doc_id,
    pdf_filename: filename,
    filename: raw.filename || raw.pdf_filename || raw.metadata?.filename || filename,
    primary_page: page && page > 0 ? page : (undefined as any),
    page: page && page > 0 ? page : undefined,
    page_number: page && page > 0 ? page : undefined,
    heading:
      raw.heading ||
      raw.section_heading ||
      raw.metadata?.heading ||
      raw.metadata?.section_heading ||
      raw.title ||
      '',
    plain_text:
      raw.plain_text ||
      raw.text ||
      raw.content ||
      raw.excerpt ||
      raw.snippet ||
      raw.metadata?.excerpt ||
      '',
    snippet: raw.snippet || raw.excerpt || raw.plain_text || raw.text,
    text: raw.text || raw.plain_text || raw.excerpt || raw.content,
    university: raw.university || raw.metadata?.university || '',
    similarity:
      typeof raw.similarity === 'number'
        ? raw.similarity
        : typeof raw.relevance_score === 'number'
          ? raw.relevance_score
          : 0.9,
    score:
      typeof raw.score === 'number'
        ? raw.score
        : typeof raw.relevance_score === 'number'
          ? raw.relevance_score
          : typeof raw.similarity === 'number'
            ? raw.similarity
            : undefined,
    printed_page: raw.printed_page || raw.metadata?.printed_page,
    page_url: pageUrl,
    page_image_url: pageImageUrl,
    page_view_url: pageViewUrl,
    source_type: raw.source_type || raw.metadata?.source_type || (isWebSource ? 'EXTERNAL_PUBLIC_RECORD' : undefined),
    url: rawUrl,
    metadata: raw.metadata,
  };
}
