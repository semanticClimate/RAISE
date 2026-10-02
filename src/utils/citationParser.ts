import type { Citation } from '../types';

export interface CitationToken {
  type: 'text' | 'citation';
  content: string;
  citationIndex?: number;
  citation?: Citation;
}

/**
 * Universal Citation Normalizer
 * Guarantees that every citation object has:
 * - A valid, 1-indexed citation_index
 * - An accurate physical PDF primary_page (recovers from page, page_number, physical_page, or chunk_id like _p020_)
 * - A clean, human-readable pdf_filename (recovers from filename, document_name, source, or defaultDocName)
 * - Clean plain_text, heading, and similarity score
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
    if (typeof cand === 'string' && !isNaN(parseInt(cand, 10))) {
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
  // NOTE: Do NOT treat parent_005 as a page number (parent_XXX is a LangChain chunk index, not a PDF page)
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
  }

  // 3. Extract citation index
  const citIdx =
    typeof raw.citation_index === 'number' && raw.citation_index > 0
      ? raw.citation_index
      : typeof raw.index === 'number' && raw.index > 0
        ? raw.index
        : indexFallback;

  return {
    citation_index: citIdx,
    chunk_id: raw.chunk_id || raw.id || raw.metadata?.chunk_id || `chk-${citIdx}`,
    document_id: raw.document_id || raw.doc_id || raw.metadata?.doc_id || filename,
    pdf_filename: filename,
    primary_page: page && page > 0 ? page : (undefined as any),
    heading: raw.heading || raw.metadata?.heading || raw.title || '',
    plain_text: raw.plain_text || raw.text || raw.content || raw.snippet || '',
    university: raw.university || raw.metadata?.university || '',
    similarity: typeof raw.similarity === 'number' ? raw.similarity : 0.9,
    printed_page: raw.printed_page || raw.metadata?.printed_page,
    page_url: raw.page_url || raw.metadata?.page_url,
    page_image_url: raw.page_image_url || raw.metadata?.page_image_url,
    page_view_url: raw.page_view_url || raw.metadata?.page_view_url,
  };
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
 * Merges adjacent citation brackets and deduplicates indices:
 * e.g.
 * - "[1] [1]" -> "[1]"
 * - "[1][1]" -> "[1]"
 * - "[1], [1]" -> "[1]"
 * - "[1] [2]" -> "[1, 2]"
 * - "[1, 2] [2]" -> "[1, 2]"
 * - "[1, 1]" -> "[1]"
 * - "Gokhale . [1]" -> "Gokhale. [1]"
 */
export function deduplicateAndMergeCitations(text: string): string {
  if (!text) return '';

  let result = text;

  // 1. Deduplicate inside compound brackets: e.g. [1, 1] -> [1], [1, 2, 1] -> [1, 2]
  result = result.replace(/\[(\d+(?:\s*,\s*\d+)+)\]/g, (_, inner) => {
    const indices = inner
      .split(',')
      .map((s: string) => Number.parseInt(s.trim(), 10))
      .filter((n: number) => !Number.isNaN(n));
    const unique = Array.from(new Set(indices));
    return `[${unique.join(', ')}]`;
  });

  // 2. Iteratively deduplicate repeated identical adjacent citation brackets:
  // Matches e.g. [1] [1], [1][1], [1], [1], [1, 2] [1, 2]
  const duplicateAdjacentRegex = /\[(\d+(?:\s*,\s*\d+)*)\](?:[ \t]*,?[ \t]*|;[ \t]*)\[\1\]/g;
  while (duplicateAdjacentRegex.test(result)) {
    result = result.replace(duplicateAdjacentRegex, '[$1]');
  }

  // Also handle single-index duplicate pairs like [1] [1]
  const duplicatePairRegex = /\[(\d+)\](?:[ \t]*,?[ \t]*|;[ \t]*)\[\1\]/g;
  while (duplicatePairRegex.test(result)) {
    result = result.replace(duplicatePairRegex, '[$1]');
  }

  // 3. Fix floating spaces before punctuation: "Gokhale . [1]" -> "Gokhale. [1]"
  result = result.replace(/\s+([.,;:!?])(\s*\[)/g, '$1$2');

  return result;
}

/**
 * Parses markdown text containing bracketed citation markers like [1], [2]
 * and matches them against the provided citations array.
 */
export function parseCitations(text: string, citations: Citation[] = []): CitationToken[] {
  if (!text) return [];

  const cleanText = deduplicateAndMergeCitations(text);
  const normalized = citations.map((c, idx) => normalizeCitation(c, idx + 1));

  // Create lookup map by citation_index
  const citationMap = new Map<number, Citation>();
  for (const c of normalized) {
    citationMap.set(c.citation_index, c);
  }

  const tokens: CitationToken[] = [];
  // Regex to match [1], [2], or compound [1, 2, 3]
  const citationRegex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = citationRegex.exec(cleanText)) !== null) {
    const matchStart = match.index;
    const matchEnd = citationRegex.lastIndex;

    // Push preceding text segment if non-empty
    if (matchStart > lastIndex) {
      tokens.push({
        type: 'text',
        content: cleanText.substring(lastIndex, matchStart),
      });
    }

    const rawIndices = match[1]
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));

    for (const citationIndex of rawIndices) {
      const matchedCitation =
        citationMap.get(citationIndex) ??
        (citationIndex > 0 && citationIndex <= normalized.length
          ? normalized[citationIndex - 1]
          : undefined);

      tokens.push({
        type: 'citation',
        content: `[${citationIndex}]`,
        citationIndex,
        citation: matchedCitation,
      });
    }

    lastIndex = matchEnd;
  }

  // Push any remaining text segment
  if (lastIndex < cleanText.length) {
    tokens.push({
      type: 'text',
      content: cleanText.substring(lastIndex),
    });
  }

  return tokens;
}

export interface CleanRagResponseResult {
  cleanText: string;
  citations: Citation[];
}

/**
 * Prunes redundant citation clutter across consecutive sentences, paragraphs, and list items.
 * Adheres to standard scholarly and academic citation practices (APA 7th §8.1, Chicago 17th §14.28):
 * - Within a paragraph/bullet: if the same citation appears multiple times across consecutive sentences,
 *   only keep the trailing citation covering the paragraph.
 * - Under a cited section or introductory topic statement: redundant repetition of the same citation
 *   on every child attribute bullet (e.g. "Patent Name", "Inventors", "Application Number") is omitted.
 * - Across consecutive bullet lists: when consecutive items share the identical citation set,
 *   the citation is retained on the introducing item or conclusion rather than repeated on every bullet.
 */
export function pruneRedundantCitations(text: string): string {
  if (!text) return '';

  const lines = text.split('\n');
  const resultLines: string[] = [];

  let currentScopeCitation: string | null = null;
  let sameCitationCount = 0;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    const trimmed = line.trim();

    // Reset scope on empty lines or major section headers (#, ##, ###)
    if (!trimmed || /^#{1,4}\s+/.test(trimmed)) {
      if (/^#{1,4}\s+/.test(trimmed)) {
        currentScopeCitation = null;
        sameCitationCount = 0;
      }
      resultLines.push(line);
      continue;
    }

    // 1. Intra-line deduplication:
    // If the exact same citation appears 2+ times on the SAME line/item:
    // e.g. "CMCNPs [1, 2]. These nanoparticles deliver siRNA... [1, 2]."
    // Keep only the concluding citation on the item.
    const allCitsOnLine = line.match(/\[\d+(?:\s*,\s*\d+)*\]/g) || [];
    if (allCitsOnLine.length > 1) {
      const counts: Record<string, number> = {};
      for (const c of allCitsOnLine) {
        counts[c] = (counts[c] || 0) + 1;
      }
      for (const [cit, count] of Object.entries(counts)) {
        if (count > 1) {
          const escaped = cit.replace(/[[\]]/g, '\\$&');
          let remaining = count;
          line = line.replace(new RegExp(`\\s*${escaped}\\s*([.,;:!?])?`, 'g'), (m, punct) => {
            remaining--;
            if (remaining === 0) {
              return m; // keep the last occurrence
            }
            return punct || '';
          });
        }
      }
    }

    // 2. Inter-line / List deduplication:
    // Extract trailing citation on this line (e.g. "... [1, 2].")
    const match = line.match(/\[(\d+(?:\s*,\s*\d+)*)\]\s*[.,;:!?]?\s*$/);
    const lineCit = match ? `[${match[1]}]` : null;

    if (lineCit) {
      const isBullet = /^(\s*[-*•]|\s*\d+\.)/.test(line);

      if (lineCit === currentScopeCitation) {
        sameCitationCount++;

        // If an introductory sentence or parent statement already cited this source set,
        // prune the redundant repetition from child attribute bullets:
        // e.g. "* Patent Name: ...", "* Inventors: ...", "* Patent Application Number: ..."
        const isAttributeBullet =
          isBullet &&
          /^\s*[-*•]\s*(\*\*)?(Patent Name|Inventors?|Application Number|Patent Application|Date|Filing Date|Assignee|Mechanism of Action|Experimental Evidence|Key Findings?|Results?|Evidence|Methods?)(\*\*)?\s*:/i.test(
            line
          );

        // Or in a list of consecutive items citing the identical source:
        if (isAttributeBullet || sameCitationCount > 1) {
          // Check if this is the concluding line of the current block
          const isNextLineDifferent =
            i + 1 >= lines.length ||
            !lines[i + 1].trim() ||
            /^#{1,4}\s+/.test(lines[i + 1].trim()) ||
            !lines[i + 1].includes(lineCit);

          // If it's an attribute bullet or intermediate bullet, prune it
          if (!isNextLineDifferent || isAttributeBullet) {
            const escaped = lineCit.replace(/[[\]]/g, '\\$&');
            line = line.replace(new RegExp(`\\s*${escaped}\\s*([.,;:!?])?$`), (_, p) => p || '');
          }
        }
      } else {
        currentScopeCitation = lineCit;
        sameCitationCount = 1;
      }
    }

    resultLines.push(line);
  }

  let res = resultLines.join('\n');
  res = res.replace(/([A-Za-z0-9])\s+\./g, '$1.');
  return res;
}

/**
 * Robust cleaner and normalizer for RAG responses.
 * 1. Strips non-printable control characters (\x00-\x08\x0B\x0C\x0E-\x1F\x7F) like backspaces from OCR/PDF extraction.
 * 2. Unpacks verbose in-text citations like `(Annual Report.pdf, Page 8) [1]:` into clean `[1]` citation markers.
 * 3. Enriches and synchronizes the citations array with filenames and page numbers discovered in text.
 * 4. Ensures proper line breaks and paragraphs around bullet lists (•) and numbered items.
 * 5. Structures list items with distinct headings and readable indented excerpt blocks.
 */
export function cleanRagResponseText(
  rawText: string,
  initialCitations: Citation[] = []
): CleanRagResponseResult {
  if (!rawText) return { cleanText: '', citations: [] };

  // Normalize unicode (e.g. mathematical bold digits [𝟏] -> [1])
  let text = rawText.normalize('NFKC');

  // 1. Strip non-printable control characters (except \t, \n, \r)
  text = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

  // Strip literal escaped control character sequences (e.g. \x08, \u0008)
  text = text.replace(
    /\\x0[0-8bBcCeEfF]|\\x1[0-9a-fA-F]|\\x7[fF]|\\u000[0-8bBcCeEfF]|\\u001[0-9a-fA-F]/g,
    ''
  );

  // 2. Normalize newlines
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // 3. Collect and normalize existing citations
  const citMap = new Map<number, Citation>();
  let maxIndex = 0;
  for (let i = 0; i < initialCitations.length; i++) {
    const norm = normalizeCitation(initialCitations[i], i + 1);
    citMap.set(norm.citation_index, norm);
    if (norm.citation_index > maxIndex) maxIndex = norm.citation_index;
  }

  let nextAllocIndex = maxIndex + 1;

  // 4. Extract and clean verbose parenthetical in-text citations
  const verboseCitationRegex =
    /(?:\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?,\s*(?:page|p\.?)\s*(\d+)[^()\n]*?|(?:page|p\.?)\s*(\d+)[^()\n]*?,\s*[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)\s*(?:\[(\d+)\])?|\[(\d+)\]\s*\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?,\s*(?:page|p\.?)\s*(\d+)[^()\n]*?|(?:page|p\.?)\s*(\d+)[^()\n]*?,\s*[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)|\((?:[^()\n]*?\.(?:pdf|docx?|txt|md|xlsx?)[^()\n]*?)\)\s*\[(\d+)\]|\((?:page|p\.?)\s*(\d+)[^()\n]*?\)\s*\[(\d+)\]|\(([^()\n]+?\.(?:pdf|docx?|txt|md|xlsx?)\s*,\s*(?:page|p\.?)\s*(\d+)[^()\n]*?)\))/gi;

  text = text.replace(verboseCitationRegex, (fullMatch) => {
    const numMatch = fullMatch.match(/\[(\d+)\]/);
    const fileMatch = fullMatch.match(/([a-zA-Z0-9_\- .]+\.(?:pdf|docx?|txt|md|xlsx?))/i);
    const pageMatch = fullMatch.match(/(?:page|p\.?)\s*(\d+)/i);

    const explicitIdx = numMatch ? parseInt(numMatch[1], 10) : null;
    const idx = explicitIdx || nextAllocIndex++;
    if (idx >= nextAllocIndex) nextAllocIndex = idx + 1;

    const filename = fileMatch ? fileMatch[1].trim() : '';
    const page = pageMatch ? parseInt(pageMatch[1], 10) : undefined;

    if (!citMap.has(idx)) {
      citMap.set(idx, {
        citation_index: idx,
        pdf_filename: filename,
        primary_page: page as any,
        chunk_id: `extracted-${idx}`,
        document_id: filename || `doc-${idx}`,
        heading: '',
        plain_text: '',
        university: '',
        similarity: 1.0,
      });
    } else {
      const existing = citMap.get(idx)!;
      if (filename && (!existing.pdf_filename || existing.pdf_filename === 'Document')) {
        existing.pdf_filename = filename;
      }
      if (page && (!existing.primary_page || existing.primary_page <= 0)) {
        existing.primary_page = page;
      }
    }

    return ` [${idx}] `;
  });

  // Normalize spacing around citation brackets: " [1] :" -> " [1]:"
  text = text.replace(/[ \t]+(\[\d+\])/g, ' $1');
  text = text.replace(/(\[\d+\])\s*:/g, '$1:');

  // Merge adjacent / repeated citations early
  text = deduplicateAndMergeCitations(text);

  // 1. Strip malformed bullet prefixes from headings early: e.g. "* ### Title" -> "### Title"
  text = text.replace(/^[ \t]*[•*-]\s*(#{1,4})/gm, '$1');

  // 2. Clean malformed headings with leading bullets and trailing stars like "• **### Title**"
  text = text.replace(
    /^[ \t]*[•*-]\s*(?:\*\*)?\s*(#{1,4})\s*([^#\n]+?)(?:\*\*)?\s*$/gm,
    '\n\n$1 $2\n\n'
  );

  // 3. Separate headings where bold title is glued to subsequent paragraph text:
  // e.g. "### **Research Study: PTBP2**A study from BRIC-ILS..." -> "### Research Study: PTBP2\n\nA study from BRIC-ILS..."
  text = text.replace(
    /^[ \t]*(?:[•*-]\s*)?(#{1,4})\s*(?:\*\*)?([^*\n]+?)\*\*\s*([A-Za-z0-9])/gm,
    '\n\n$1 $2\n\n$3'
  );

  // 3. Clean malformed headings with wrapping/trailing asterisks like "### **Title**" or "### Title**"
  text = text.replace(/^(#{1,4})\s*(?:\*\*)?\s*([^*\n]+?)\s*(?:\*\*)?\s*$/gm, '$1 $2');

  // 4. Clean standalone section titles into clean H3 markdown headings
  text = text.replace(
    /^[ \t]*(?:\*\*)?\s*(Key Strategic Conclusions|Institutional Strategic Outcomes|Overarching Institutional Conclusions|Strategic Framework and Economic Targets)(?:\*\*)?[ \t]*$/gm,
    '\n\n### $1\n\n'
  );

  // 5. Separate standalone bold section titles glued directly to body text on the same line:
  // e.g. "**Patent: Biomimetic Polymeric Nanoformulation**The report highlights..." -> "### Patent: Biomimetic Polymeric Nanoformulation\n\nThe report highlights..."
  text = text.replace(/^[ \t]*\*\*([A-Z][^*\n]{3,80}?)\*\*\s*([A-Z][a-z]+)/gm, '\n\n### $1\n\n$2');

  // 6. Separate headings running directly into sentence words without newline/space:
  // e.g. "### Patent: Biomimetic Polymeric Nanoformulation for OsteosarcomaThe report highlights..."
  // -> "### Patent: Biomimetic Polymeric Nanoformulation for Osteosarcoma\n\nThe report highlights..."
  text = text.replace(
    /^(#{1,4}\s+[A-Za-z0-9\s:—–-]{5,80}?[a-z0-9])([A-Z][a-z]+\s+(?:report|study|paper|findings?|data|analysis|investigates|demonstrates|presents|highlights|reveals|shows|concludes|from|in|is|are|was|were|aims|focuses|describes|utilizes|developed|designed)\b)/gm,
    '$1\n\n$2'
  );

  // Separate bullets onto distinct lines (including glued bullets without space)
  text = text.replace(/([^\n])\s*•\s*/g, '$1\n\n• ');
  text = text.replace(/\s*•\s*/g, '\n\n• ').trim();

  // Support standard Markdown hyphens (- ) and asterisks (* ) as well
  text = text.replace(/([^\n])\n(- \*\*)/g, '$1\n\n$2');
  text = text.replace(/([^\n])\n(-\s+)/g, '$1\n\n$2');
  text = text.replace(/([^\n])\n(\*\s+)/g, '$1\n\n$2');
  text = text.replace(/([^\n])\s*-\s+\*\*/g, '$1\n\n- **');

  // Clean title + citation + colon followed by space(s) into clean indented layout
  text = text.replace(
    /([•-])\s*(\*\*[^*]+\*\*)\s*(\[\d+\])?\s*[:—–-]?\s+/g,
    (_, bullet, title, cit) => {
      return `${bullet} ${title}${cit ? ` ${cit}` : ''}\n  `;
    }
  );

  // Separate numbered lists that were inline (e.g., "Intro: 1. **Title**")
  text = text.replace(/([.:;!?])\s+(\d+\.)\s+\*\*/g, '$1\n\n$2 **');
  text = text.replace(/([^\n])\n(\d+\.\s+\*\*)/g, '$1\n\n$2');

  // Strip trailing whitespace per line and collapse 3+ consecutive linebreaks to 2
  text = text.replace(/[ \t]+$/gm, '');
  text = text.replace(/\n{3,}/g, '\n\n');

  // If the text does not contain any inline citation markers but citations exist,
  // append citations at the end of the text so the user can always inspect them
  if (!/\[\d+\]/.test(text) && citMap.size > 0) {
    const badges = Array.from(new Set(citMap.keys()))
      .sort((a, b) => a - b)
      .map((idx) => `[${idx}]`)
      .join(' ');
    text = `${text.trim()} ${badges}`;
  }

  // Final deduplication & merging of citation markers and floating punctuation
  text = deduplicateAndMergeCitations(text);
  text = pruneRedundantCitations(text);

  return { cleanText: text, citations: Array.from(citMap.values()) };
}
