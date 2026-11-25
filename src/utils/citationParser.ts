import type { Citation } from '../types';
import {
  extractVerifiedPageNumber,
  normalizeCitation,
  stripCitationsForCopy,
} from './citationNormalizer';
import { getCopyableAnswerText } from './reasoningParser';
import { preserveMarkdownTables } from './sanitizeStreamText';

export { extractVerifiedPageNumber, normalizeCitation, stripCitationsForCopy };

export interface CitationToken {
  type: 'text' | 'citation';
  content: string;
  citationIndex?: number;
  citation?: Citation;
}

export interface CleanRagResponseResult {
  cleanText: string;
  citations: Citation[];
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
  // Using prev !== result to avoid stateful /g lastIndex fighting
  const duplicateAdjacentRegex = /\[(\d+(?:\s*,\s*\d+)*)\](?:[ \t]*,?[ \t]*|;[ \t]*)\[\1\]/g;
  let prev = '';
  while (prev !== result) {
    prev = result;
    result = result.replace(duplicateAdjacentRegex, '[$1]');
  }

  // Also handle single-index duplicate pairs like [1] [1]
  const duplicatePairRegex = /\[(\d+)\](?:[ \t]*,?[ \t]*|;[ \t]*)\[\1\]/g;
  prev = '';
  while (prev !== result) {
    prev = result;
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
      .filter((n) => !Number.isNaN(n));

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

/**
 * Prunes redundant citation clutter across consecutive sentences, paragraphs, and list items.
 */
export function pruneRedundantCitations(text: string): string {
  if (!text) return '';

  const lines = text.split('\n');
  const resultLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    const trimmed = line.trim();

    // Preserve headers and empty lines
    if (!trimmed || /^#{1,4}\s+/.test(trimmed)) {
      resultLines.push(line);
      continue;
    }

    // Intra-line deduplication:
    // If the exact same citation appears 2+ times on the SAME line:
    // e.g. "CMCNPs [1]. These nanoparticles deliver siRNA [1]."
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

    resultLines.push(line);
  }

  let res = resultLines.join('\n');
  res = res.replace(/([A-Za-z0-9])\s+\./g, '$1.');
  return res;
}

// LRU Memoization Cache for cleanRagResponseText
interface CleanRagCacheEntry {
  rawText: string;
  result: CleanRagResponseResult;
}

const MAX_CACHE = 64;
const cleanRagCache = new Map<string, CleanRagCacheEntry>();

function getCacheKey(rawText: string, citationsLength: number): string {
  return `${rawText.length}:${rawText.slice(0, 64)}:${rawText.slice(-64)}:${citationsLength}`;
}

/**
 * Robust cleaner and normalizer for RAG responses.
 * 1. Strips non-printable control characters with single zero-allocation regex.
 * 2. Temporarily masks fenced code blocks (```...```) and math blocks ($$...$$).
 * 3. Fast-path guards verbose citation extraction.
 * 4. Deduplicates and formats citations and markdown structure.
 * 5. Uses LRU memoization (MAX_CACHE = 64) for instantaneous re-renders.
 */
export function cleanRagResponseText(
  rawText: string,
  initialCitations: Citation[] = [],
  options: { preserveReasoningTags?: boolean } = {}
): CleanRagResponseResult {
  if (!rawText) return { cleanText: '', citations: [] };

  const effectiveRawText =
    !options.preserveReasoningTags && /<(?:think|thought|reasoning)\b|<\/(?:think|thought|reasoning)>/i.test(rawText)
      ? getCopyableAnswerText(rawText)
      : rawText;

  const cacheKey = getCacheKey(effectiveRawText, initialCitations.length);
  const cached = cleanRagCache.get(cacheKey);
  if (cached && cached.rawText === effectiveRawText) {
    // Refresh LRU order
    cleanRagCache.delete(cacheKey);
    cleanRagCache.set(cacheKey, cached);
    return cached.result;
  }

  // Normalize unicode (e.g. mathematical bold digits [𝟏] -> [1])
  let text = effectiveRawText.normalize('NFKC');

  // 1. Strip non-printable control characters with zero-allocation regex
  text = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

  // Strip literal escaped control character sequences (e.g. \x08, \u0008)
  text = text.replace(
    /\\x0[0-8bBcCeEfF]|\\x1[0-9a-fA-F]|\\x7[fF]|\\u000[0-8bBcCeEfF]|\\u001[0-9a-fA-F]/g,
    ''
  );

  // 2. Normalize newlines
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // 3. Mask fenced code blocks and $$ math blocks before structural regexes
  const codeBlocks: string[] = [];
  text = text.replace(/```[\s\S]*?```|\$\$[\s\S]*?\$\$/g, (match) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push(match);
    return placeholder;
  });

  // 4. Collect and normalize existing citations
  const citMap = new Map<number, Citation>();
  let maxIndex = 0;
  for (let i = 0; i < initialCitations.length; i++) {
    const norm = normalizeCitation(initialCitations[i], i + 1);
    citMap.set(norm.citation_index, norm);
    if (norm.citation_index > maxIndex) maxIndex = norm.citation_index;
  }

  let nextAllocIndex = maxIndex + 1;

  // 5. Fast-path guard around verbose parenthetical in-text citations
  if (
    text.includes('(') &&
    (/\.(?:pdf|docx?|txt|md|xlsx?)\b/i.test(text) || /(?:page|p\.?)\s*\d+/i.test(text))
  ) {
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
          primary_page: page,
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
  }

  // Normalize spacing around citation brackets: " [1] :" -> " [1]:"
  text = text.replace(/[ \t]+(\[\d+\])/g, ' $1');
  text = text.replace(/(\[\d+\])\s*:/g, '$1:');

  // Merge adjacent / repeated citations early
  text = deduplicateAndMergeCitations(text);

  // Protect Markdown tables while repairing inline headings and glued bullet spacing
  text = preserveMarkdownTables(text, (prose) => {
    let formatted = prose;

    // Clean headings and structure
    formatted = formatted.replace(/^[ \t]*[•*-]\s*(#{1,4})/gm, '$1');
    formatted = formatted.replace(
      /^[ \t]*[•*-]\s*(?:\*\*)?\s*(#{1,4})\s*([^#\n]+?)(?:\*\*)?\s*$/gm,
      '\n\n$1 $2\n\n'
    );
    formatted = formatted.replace(
      /^[ \t]*(?:[•*-]\s*)?(#{1,4})\s*(?:\*\*)?([^*\n]+?)\*\*\s*([A-Za-z0-9])/gm,
      '\n\n$1 $2\n\n$3'
    );
    formatted = formatted.replace(/^(#{1,4})\s*(?:\*\*)?\s*([^*\n]+?)\s*(?:\*\*)?\s*$/gm, '$1 $2');
    formatted = formatted.replace(
      /^[ \t]*(?:\*\*)?\s*(Key Strategic Conclusions|Institutional Strategic Outcomes|Overarching Institutional Conclusions|Strategic Framework and Economic Targets)(?:\*\*)?[ \t]*$/gm,
      '\n\n### $1\n\n'
    );
    formatted = formatted.replace(/^[ \t]*\*\*([A-Z][^*\n]{3,80}?)\*\*\s*([A-Z][a-z]+)/gm, '\n\n### $1\n\n$2');
    formatted = formatted.replace(
      /^(#{1,4}\s+[A-Za-z0-9\s:—–-]{5,80}?[a-z0-9])([A-Z][a-z]+\s+(?:report|study|paper|findings?|data|analysis|investigates|demonstrates|presents|highlights|reveals|shows|concludes|from|in|is|are|was|were|aims|focuses|describes|utilizes|developed|designed)\b)/gm,
      '$1\n\n$2'
    );

    // Separate bullets onto distinct lines
    formatted = formatted.replace(/([^\n])\s*•\s*/g, '$1\n\n• ');
    formatted = formatted.replace(/\s*•\s*/g, '\n\n• ').trim();

    // Support standard Markdown hyphens (- ) and asterisks (* )
    formatted = formatted.replace(/([^\n])\n(- \*\*)/g, '$1\n\n$2');
    formatted = formatted.replace(/([^\n])\n(-\s+)/g, '$1\n\n$2');
    formatted = formatted.replace(/([^\n])\n(\*\s+)/g, '$1\n\n$2');
    formatted = formatted.replace(/([^\n])\s*-\s+\*\*/g, '$1\n\n- **');

    // Clean title + citation + colon
    formatted = formatted.replace(
      /([•-])\s*(\*\*[^*]+\*\*)\s*(\[\d+\])?\s*[:—–-]?\s+/g,
      (_, bullet, title, cit) => {
        return `${bullet} ${title}${cit ? ` ${cit}` : ''}\n  `;
      }
    );

    // Separate numbered lists that were inline
    formatted = formatted.replace(/([.:;!?])\s+(\d+\.)\s+\*\*/g, '$1\n\n$2 **');
    formatted = formatted.replace(/([^\n])\n(\d+\.\s+\*\*)/g, '$1\n\n$2');

    // Strip trailing whitespace per line and collapse 3+ consecutive linebreaks to 2
    formatted = formatted.replace(/[ \t]+$/gm, '');
    return formatted.replace(/\n{3,}/g, '\n\n');
  });

  // If the text does not contain any inline citation markers but citations exist,
  // append citations at the end of the text
  if (!/\[\d+\]/.test(text) && citMap.size > 0) {
    const badges = Array.from(new Set(citMap.keys()))
      .sort((a, b) => a - b)
      .map((idx) => `[${idx}]`)
      .join(' ');
    text = `${text.trim()} ${badges}`;
  }

  // Final deduplication & merging of citation markers
  text = deduplicateAndMergeCitations(text);
  text = pruneRedundantCitations(text);

  // Restore masked code blocks and math blocks
  if (codeBlocks.length > 0) {
    text = text.replace(/__CODE_BLOCK_(\d+)__/g, (_, idx) => {
      const bIdx = parseInt(idx, 10);
      return codeBlocks[bIdx] !== undefined ? codeBlocks[bIdx] : _;
    });
  }

  const result: CleanRagResponseResult = {
    cleanText: text,
    citations: Array.from(citMap.values()),
  };

  // Cache result in LRU
  if (cleanRagCache.size >= MAX_CACHE) {
    const oldestKey = cleanRagCache.keys().next().value;
    if (oldestKey) cleanRagCache.delete(oldestKey);
  }
  cleanRagCache.set(cacheKey, { rawText: effectiveRawText, result });

  return result;
}
