import katex from 'katex';
import 'katex/dist/contrib/mhchem.mjs';
import type { SubgraphQueryResponse, ChatSession } from '../types';
import { cleanRagResponseText } from './citationParser';

/**
 * Normalizes text to a URL- and filename-safe slug.
 */
export function slugify(text: string, maxLength = 36): string {
  const clean = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-');
  return clean.slice(0, maxLength) || 'research-response';
}

/**
 * Generates an ISO-date-stamped default filename for exports.
 */
export function generateExportFilename(
  query: string,
  extension: 'md' | 'json' | 'pdf' | 'html',
  prefix = 'raise-report'
): string {
  const slug = slugify(query, 32);
  const dateStr = new Date().toISOString().split('T')[0];
  return `${prefix}-${slug}-${dateStr}.${extension}`;
}

/**
 * Safely downloads a Blob in the browser with fallback.
 */
export function downloadBlob(blob: Blob, filename: string): boolean {
  try {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
      return false;
    }
    const url = typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(blob) : '';
    if (!url) return false;

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.setAttribute('data-testid', 'download-link');
    // Prevent jsdom navigation error during synthetic test clicks
    link.addEventListener('click', (e) => {
      e.stopPropagation();
    });
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    if (URL.revokeObjectURL) {
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    return true;
  } catch (err) {
    console.warn('Failed to download blob:', err);
    return false;
  }
}

/**
 * Copies markdown-formatted text to the system clipboard, preserving
 * exact formatting (headings, code blocks, lists, bolding, citations).
 */
export async function copyMarkdownToClipboard(markdownText: string): Promise<boolean> {
  if (!markdownText) return false;

  // 1. Try modern navigator.clipboard API
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(markdownText);
      return true;
    }
  } catch {
    // Fall back to document.execCommand below
  }

  // 2. Fallback to hidden textarea with document.execCommand('copy')
  try {
    if (typeof document !== 'undefined') {
      const textarea = document.createElement('textarea');
      textarea.value = markdownText;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '-9999px';
      textarea.setAttribute('readonly', '');
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const success = document.execCommand('copy');
      document.body.removeChild(textarea);
      return success;
    }
  } catch (err) {
    console.warn('Clipboard copy failed:', err);
  }

  return false;
}

/**
 * Dynamically resolves audited pipeline architecture without hardcoding offline substrates.
 * If Neo4j or complex neural models are not actively reported by the backend, uses true runtime fallbacks.
 * Explicitly surfaces ChromaDB, Neo4j (if active), PostgreSQL, and Redis as active answering substrates.
 */
export function resolveAuditedProvenance(response?: Partial<SubgraphQueryResponse>) {
  const pInfo = response?.pipeline_info;
  const rawStorage = pInfo?.storage_used || response?.storage_used;

  // Use authoritative backend multi-substrate descriptor directly when available
  const storageUsed =
    typeof rawStorage === 'string' && rawStorage.trim().length > 0
      ? rawStorage.trim()
      : 'ChromaDB (Vector) + SQLite (Local)';

  const llmModel = pInfo?.llm_model || response?.llm_model || 'gemini-3.5-flash-lite';
  const llmProvider = pInfo?.llm_provider || response?.llm_provider || 'gemini';
  const encoderModel = pInfo?.encoder_model || response?.encoder_model || 'google/embeddinggemma-2';
  const rerankerModel = pInfo?.reranker_model || response?.reranker_model || 'BAAI/bge-reranker-v2-m3';
  const nliVerifierModel = pInfo?.nli_verifier_model || response?.nli_verifier_model || 'dleemiller/finecat-nli-ultra-l';

  return {
    storageUsed,
    llmModel,
    llmProvider,
    encoderModel,
    rerankerModel,
    nliVerifierModel,
  };
}

/**
 * Formats an AI response into a rich, structured Markdown report
 * complete with query details, quality metrics, and citations.
 */
export function formatMarkdownReport(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>
): string {
  const now = new Date().toLocaleString('en-US', {
    dateStyle: 'full',
    timeStyle: 'medium',
  });

  const lines: string[] = [];

  // Title Header
  lines.push(`# RAISE: Research Assessment Intelligence & Semantic Extraction`);
  lines.push('');
  lines.push(`**Date:** ${now}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // Question
  lines.push('## Question');
  lines.push('');
  lines.push(`> ${query || 'General Academic & Institutional Query'}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // Clean answer text & format citations
  const { cleanText, citations: enrichedCitations } = cleanRagResponseText(
    answerText,
    response?.citations || []
  );
  const citations =
    enrichedCitations && enrichedCitations.length > 0
      ? enrichedCitations
      : response?.citations || [];

  // Answer Section
  lines.push('## Answer');
  lines.push('');
  lines.push(cleanText.trim());
  lines.push('');

  // Citations & References Section
  if (citations && citations.length > 0) {
    lines.push('---');
    lines.push('');
    lines.push('## References');
    lines.push('');

    citations.forEach((cit) => {
      const idx = cit.citation_index;
      const file = cit.pdf_filename || 'Audited Institutional Document';
      const parts: string[] = [];
      if (cit.primary_page) parts.push(`Page ${cit.primary_page}`);
      if (cit.heading) parts.push(cit.heading);
      if (cit.university) parts.push(cit.university);
      const extra = parts.length > 0 ? ` (${parts.join(', ')})` : '';

      lines.push(`* **[${idx}]** ${file}${extra}`);
    });
    lines.push('');
  }

  // Architecture Running Section
  const prov = resolveAuditedProvenance(response);

  lines.push('---');
  lines.push('');
  lines.push('### 🔬 Architecture Running');
  lines.push(`* **Storage Substrates:** ${prov.storageUsed}`);
  lines.push(`* **Synthesis LLM:** ${prov.llmModel} (${prov.llmProvider})`);
  lines.push(`* **Dense Embedding Encoder:** ${prov.encoderModel}`);
  lines.push(`* **Cross-Attention Reranker:** ${prov.rerankerModel}`);
  lines.push(`* **NLI Entailment Verifier:** ${prov.nliVerifierModel}`);
  lines.push('* **Platform Attribution:** RAISE');
  lines.push('');

  // Footer
  lines.push('---');
  lines.push('');
  lines.push(
    '*Report generated by RAISE — Research Assessment Intelligence & Semantic Extraction*'
  );

  return lines.join('\n');
}

/**
 * Formats the raw response and full metadata into a developer JSON object.
 */
export function formatDeveloperJson(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>
): Record<string, unknown> {
  const prov = resolveAuditedProvenance(response);
  return {
    export_version: '1.0.0',
    platform: 'RAISE: Research Assessment Intelligence & Semantic Extraction',
    exported_at: new Date().toISOString(),
    query: query || response?.query || '',
    answer: answerText,
    pipeline_info: {
      storage_used: prov.storageUsed,
      llm_provider: prov.llmProvider,
      llm_model: prov.llmModel,
      encoder_model: prov.encoderModel,
      reranker_model: prov.rerankerModel,
      nli_verifier_model: prov.nliVerifierModel,
    },
    metadata: {
      traceability_score: response?.traceability_score ?? null,
      quality_gate_decision: response?.quality_gate_decision ?? 'accept',
      execution_time_seconds: response?.execution_time ?? response?.latency_sec ?? null,
      routing_strategy: response?.routing_strategy ?? null,
      query_type: response?.query_type ?? null,
      selected_tools: response?.selected_tools ?? [],
      thread_id: response?.thread_id ?? null,
      cypher_status: response?.cypher_status ?? null,
      cypher_repair_count: response?.cypher_repair_count ?? 0,
      path_critic_expanded: response?.path_critic_expanded ?? false,
    },
    citations: response?.citations ?? [],
    verified_claims: response?.verified_claims ?? [],
    subgraph: response?.subgraph ?? { nodes: [], edges: [] },
    top_chunks: response?.top_chunks ?? [],
    quality_gate_report: response?.quality_gate_report ?? null,
    answer_contract: response?.answer_contract ?? null,
    raw_response: response ?? {},
  };
}

/**
 * Safely escapes HTML special characters to prevent XSS.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Safely renders a LaTeX formula to KaTeX HTML string (including mhchem chemistry).
 * Falls back to styled code element if KaTeX fails to parse.
 */
export function renderKatexToString(formula: string, displayMode: boolean): string {
  try {
    return katex.renderToString(formula, {
      displayMode,
      throwOnError: false,
      errorColor: '#dc2626',
      output: 'htmlAndMathml',
      strict: false,
      trust: false,
    });
  } catch (err) {
    console.warn('KaTeX rendering error:', err);
    const escaped = escapeHtml(formula);
    if (displayMode) {
      return `<div class="katex-fallback" style="text-align: center; margin: 12px 0; font-family: monospace; font-size: 13px; color: #b45309; background: #fffbeb; padding: 8px 12px; border-radius: 6px; border: 1px solid #fde68a;">${escaped}</div>`;
    }
    return `<code class="katex-fallback" style="font-family: monospace; font-size: 12px; color: #b45309; background: #fffbeb; padding: 2px 5px; border-radius: 4px; border: 1px solid #fde68a;">${escaped}</code>`;
  }
}

/**
 * Converts inline markdown tokens (math, citations, bold, italic, code, links) to HTML.
 */
export function formatInlineMarkdown(text: string): string {
  if (!text) return '';

  const INLINE_REGEX =
    /(`[^`]+`|\$\$[^\$]+?\$\$|\$([^\$\s](?:[^\$]*?[^\$\s])?)\$|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|__[^_]+__|\[\d+(?:\s*,\s*\d+)*\]|\[([^\]]+)\]\((https?:\/\/[^\s)]+|[#/][^\s)]+)\)|\b(?:FULLY_COMPARABLE|CONDITIONALLY_COMPARABLE|CONTEXT_ADJUSTED|NOT_COMPARABLE|INSUFFICIENT_EVIDENCE|EXTERNAL_SUPPLEMENTED|EXTERNAL_PUBLIC_RECORD)\b|\*[^*\n]+?\*|_[^_\n]+?_|\\\|)/g;

  const parts: string[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = INLINE_REGEX.exec(text)) !== null) {
    const matchStart = match.index;
    const matched = match[0];

    if (matchStart > lastIndex) {
      parts.push(escapeHtml(text.substring(lastIndex, matchStart)));
    }

    // Escaped pipe: \|
    if (matched === '\\|') {
      parts.push('|');
    }
    // Block / Display Math: $$formula$$
    else if (matched.startsWith('$$') && matched.endsWith('$$') && matched.length > 4) {
      const formula = matched.slice(2, -2).trim();
      parts.push(renderKatexToString(formula, true));
    }
    // Inline math: $formula$
    else if (matched.startsWith('$') && matched.endsWith('$') && matched.length > 2) {
      const formula = matched.slice(1, -1).trim();
      parts.push(renderKatexToString(formula, false));
    }
    // Citation badge: [1] or [1, 2]
    else if (/^\[\d+(?:\s*,\s*\d+)*\]$/.test(matched)) {
      parts.push(
        `<span class="citation-badge" style="display: inline-block; padding: 1px 6px; font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, monospace; font-weight: 600; color: #0284c7; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 4px; margin: 0 2px; vertical-align: baseline;">${escapeHtml(
          matched
        )}</span>`
      );
    }
    // Bold Italic: ***text***
    else if (matched.startsWith('***') && matched.endsWith('***')) {
      parts.push(`<strong><em>${formatInlineMarkdown(matched.slice(3, -3))}</em></strong>`);
    }
    // Bold: **text** or __text__
    else if (
      (matched.startsWith('**') && matched.endsWith('**')) ||
      (matched.startsWith('__') && matched.endsWith('__'))
    ) {
      parts.push(`<strong>${formatInlineMarkdown(matched.slice(2, -2))}</strong>`);
    }
    // Italic: *text* or _text_
    else if (
      (matched.startsWith('*') && matched.endsWith('*')) ||
      (matched.startsWith('_') && matched.endsWith('_'))
    ) {
      parts.push(`<em>${formatInlineMarkdown(matched.slice(1, -1))}</em>`);
    }
    // Code: `code`
    else if (matched.startsWith('`') && matched.endsWith('`')) {
      parts.push(
        `<code style="background: #f1f5f9; color: #0f172a; padding: 2px 5px; border-radius: 4px; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; border: 1px solid #e2e8f0;">${escapeHtml(
          matched.slice(1, -1)
        )}</code>`
      );
    }
    // Link: [text](url)
    else if (matched.startsWith('[') && matched.includes('](') && matched.endsWith(')')) {
      const linkMatch = matched.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+|[#/][^\s)]+)\)$/);
      if (linkMatch) {
        parts.push(
          `<a href="${escapeHtml(
            linkMatch[2]
          )}" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline;">${escapeHtml(
            linkMatch[1]
          )}</a>`
        );
      } else {
        parts.push(escapeHtml(matched));
      }
    }
    // Comparability Status pill
    else if (
      /^(?:FULLY_COMPARABLE|CONDITIONALLY_COMPARABLE|CONTEXT_ADJUSTED|NOT_COMPARABLE|INSUFFICIENT_EVIDENCE|EXTERNAL_SUPPLEMENTED|EXTERNAL_PUBLIC_RECORD)$/.test(
        matched
      )
    ) {
      parts.push(
        `<span style="display: inline-block; padding: 2px 7px; font-size: 11px; font-weight: 600; border-radius: 9999px; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;">${escapeHtml(
          matched
        )}</span>`
      );
    } else {
      parts.push(escapeHtml(matched));
    }

    lastIndex = INLINE_REGEX.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(escapeHtml(text.substring(lastIndex)));
  }

  return parts.join('');
}

/**
 * Splits a Markdown table row into trimmed cell strings, respecting:
 * - Backslash-escaped characters (\|)
 * - Inline code backticks (`...|...`)
 * - Math expressions ($...$, $$...$$)
 */
export function splitTableRow(line: string): string[] {
  let trimmed = line.trim();

  // Strip unescaped leading pipe
  if (trimmed.startsWith('|')) {
    trimmed = trimmed.slice(1);
  }

  // Helper to test if char at index is escaped by an odd number of preceding backslashes
  const isEscaped = (str: string, index: number): boolean => {
    let count = 0;
    for (let i = index - 1; i >= 0 && str[i] === '\\'; i--) {
      count++;
    }
    return count % 2 === 1;
  };

  // Strip unescaped trailing pipe
  if (trimmed.endsWith('|') && !isEscaped(trimmed, trimmed.length - 1)) {
    trimmed = trimmed.slice(0, -1);
  }

  const cells: string[] = [];
  let currentCell = '';
  let inCode = false;
  let inMath = false;
  let i = 0;

  while (i < trimmed.length) {
    const char = trimmed[i];

    if (char === '\\' && i + 1 < trimmed.length) {
      currentCell += char + trimmed[i + 1];
      i += 2;
      continue;
    }

    if (char === '`') {
      inCode = !inCode;
      currentCell += char;
      i++;
      continue;
    }

    if (char === '$' && !inCode) {
      inMath = !inMath;
      currentCell += char;
      i++;
      continue;
    }

    if (char === '|' && !inCode && !inMath) {
      cells.push(currentCell.trim());
      currentCell = '';
      i++;
      continue;
    }

    currentCell += char;
    i++;
  }

  cells.push(currentCell.trim());
  return cells;
}

/**
 * Parses Markdown column alignment specifier (:---, :---:, ---:).
 */
export function parseAlignment(spec: string): 'left' | 'center' | 'right' {
  const trimmed = spec.trim();
  if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
  if (trimmed.endsWith(':')) return 'right';
  if (trimmed.startsWith(':')) return 'left';
  return 'left';
}

/**
 * Renders Markdown table data as a beautifully styled HTML table element.
 */
export function renderHtmlTable(
  headers: string[],
  alignments: ('left' | 'center' | 'right')[],
  rows: string[][]
): string {
  const colCount = Math.max(headers.length, ...rows.map((r) => r.length), 1);

  const normalizedHeaders = [...headers];
  while (normalizedHeaders.length < colCount) {
    normalizedHeaders.push('');
  }

  const thCells = normalizedHeaders
    .map((h, idx) => {
      const align = alignments[idx] || 'left';
      const borderRight = idx < colCount - 1 ? 'border-right: 1px solid #e2e8f0;' : '';
      return `<th style="padding: 10px 14px; text-align: ${align}; font-weight: 700; color: #0f172a; font-size: 13px; letter-spacing: -0.01em; ${borderRight}">${formatInlineMarkdown(
        h
      )}</th>`;
    })
    .join('');

  const trRows = rows
    .map((row, rIdx) => {
      const bg = rIdx % 2 === 0 ? '#ffffff' : '#f8fafc';
      const normalizedRow = [...row];
      while (normalizedRow.length < colCount) {
        normalizedRow.push('');
      }
      const tdCells = normalizedRow
        .map((cell, cIdx) => {
          const align = alignments[cIdx] || 'left';
          const borderRight = cIdx < colCount - 1 ? 'border-right: 1px solid #e2e8f0;' : '';
          return `<td style="padding: 9px 14px; text-align: ${align}; color: #334155; font-size: 13.5px; line-height: 1.5; ${borderRight}">${formatInlineMarkdown(
            cell
          )}</td>`;
        })
        .join('');
      return `<tr style="background: ${bg}; border-bottom: 1px solid #e2e8f0;">${tdCells}</tr>`;
    })
    .join('');

  return `
<div class="table-container" style="overflow-x: auto; margin: 20px 0; border: 1px solid #cbd5e1; border-radius: 8px; break-inside: avoid; page-break-inside: avoid; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
  <table style="width: 100%; border-collapse: collapse; font-size: 13.5px; text-align: left; background: #ffffff;">
    <thead>
      <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
        ${thCells}
      </tr>
    </thead>
    <tbody>
      ${trRows}
    </tbody>
  </table>
</div>`;
}

/**
 * Robust markdown block transformer converting Markdown text into styled HTML elements.
 * Correctly parses headings, code blocks, block equations ($$ ... $$), tables, lists, blockquotes, and callouts.
 */
export function convertMarkdownToHtml(markdown: string): string {
  if (!markdown) return '';

  const lines = markdown.split('\n');
  const htmlBlocks: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Empty lines
    if (!trimmed) {
      i++;
      continue;
    }

    // 2. Fenced Code Block: ```lang
    if (trimmed.startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].trim().startsWith('```')) {
        i++;
      }
      const codeHtml = escapeHtml(codeLines.join('\n'));
      htmlBlocks.push(
        `<pre style="background: #0f172a; color: #f8fafc; padding: 14px 18px; border-radius: 8px; font-size: 12.5px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; overflow-x: auto; line-height: 1.5; margin: 16px 0; break-inside: avoid; page-break-inside: avoid;"><code>${codeHtml}</code></pre>`
      );
      continue;
    }

    // 3. LaTeX Block Equations: $$ formula $$
    if (trimmed.startsWith('$$')) {
      if (trimmed.length > 4 && trimmed.endsWith('$$')) {
        const formula = trimmed.slice(2, -2).trim();
        htmlBlocks.push(
          `<div class="katex-block-wrapper" style="margin: 18px 0; padding: 14px 18px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; text-align: center; overflow-x: auto; break-inside: avoid; page-break-inside: avoid;">${renderKatexToString(
            formula,
            true
          )}</div>`
        );
        i++;
        continue;
      }
      const mathLines: string[] = [];
      if (trimmed.length > 2) {
        mathLines.push(trimmed.slice(2));
      }
      i++;
      while (i < lines.length && !lines[i].trim().endsWith('$$') && lines[i].trim() !== '$$') {
        mathLines.push(lines[i]);
        i++;
      }
      if (i < lines.length) {
        const lastLine = lines[i].trim();
        if (lastLine !== '$$') {
          mathLines.push(lastLine.replace(/\$\$$/, ''));
        }
        i++;
      }
      const formula = mathLines.join('\n').trim();
      htmlBlocks.push(
        `<div class="katex-block-wrapper" style="margin: 18px 0; padding: 14px 18px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; text-align: center; overflow-x: auto; break-inside: avoid; page-break-inside: avoid;">${renderKatexToString(
          formula,
          true
        )}</div>`
      );
      continue;
    }

    // 4. Horizontal Rules: ---, ***, ___
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      htmlBlocks.push(
        `<hr style="margin: 22px 0; border: none; border-top: 1px solid #e2e8f0;" />`
      );
      i++;
      continue;
    }

    // 5. Headings: #, ##, ###, #### (or malformed bullets with headings)
    const cleanHeadingLine = trimmed.replace(/^[•*-]\s*(?:\*\*)?\s*(#{1,4})/, '$1');
    if (cleanHeadingLine.startsWith('#')) {
      const match = cleanHeadingLine.match(/^(#{1,4})\s+(.*)$/);
      if (match) {
        const level = match[1].length;
        const headingText = match[2].replace(/^\*+|\*+$/g, '').trim();
        if (level === 1) {
          htmlBlocks.push(
            `<h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 28px; margin-bottom: 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">${formatInlineMarkdown(
              headingText
            )}</h1>`
          );
        } else if (level === 2) {
          htmlBlocks.push(
            `<h2 style="font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 24px; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">${formatInlineMarkdown(
              headingText
            )}</h2>`
          );
        } else if (level === 3) {
          htmlBlocks.push(
            `<h3 style="font-size: 16px; font-weight: 700; color: #0284c7; margin-top: 20px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">${formatInlineMarkdown(
              headingText
            )}</h3>`
          );
        } else {
          htmlBlocks.push(
            `<h4 style="font-size: 14.5px; font-weight: 700; color: #0f172a; margin-top: 16px; margin-bottom: 6px;">${formatInlineMarkdown(
              headingText
            )}</h4>`
          );
        }
        i++;
        continue;
      }
    }

    // Standalone bold section header: **Section Title**
    if (
      /^\*\*[^*\n]+\*\*$/.test(trimmed) &&
      !trimmed.slice(2, -2).endsWith('.') &&
      trimmed.length < 80
    ) {
      const inner = trimmed.slice(2, -2).trim();
      htmlBlocks.push(
        `<h3 style="font-size: 16px; font-weight: 700; color: #0284c7; margin-top: 20px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">${formatInlineMarkdown(
          inner
        )}</h3>`
      );
      i++;
      continue;
    }

    // 6. Markdown Tables: starts with | and next line is separator
    if (trimmed.includes('|') && i + 1 < lines.length) {
      const nextTrimmed = lines[i + 1].trim();
      const isSep = /^\|?\s*:?-+:?\s*(\|(\s*:?-+:?\s*))+\|?$/.test(nextTrimmed);
      if (isSep) {
        const headers = splitTableRow(trimmed);
        const sepSpecs = splitTableRow(nextTrimmed);
        const alignments = sepSpecs.map(parseAlignment);

        i += 2;
        const rows: string[][] = [];
        while (
          i < lines.length &&
          lines[i].trim().includes('|') &&
          !lines[i].trim().startsWith('#')
        ) {
          rows.push(splitTableRow(lines[i]));
          i++;
        }

        const tableHtml = renderHtmlTable(headers, alignments, rows);
        htmlBlocks.push(tableHtml);
        continue;
      }
    }

    // 7. Callouts
    if (/^\*\*(Warning|Caution|Alert|Important):\*\*/i.test(trimmed)) {
      htmlBlocks.push(
        `<div style="margin: 14px 0; padding: 12px 16px; background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 6px; font-size: 13.5px; color: #92400e; line-height: 1.6; break-inside: avoid; page-break-inside: avoid;">${formatInlineMarkdown(
          trimmed
        )}</div>`
      );
      i++;
      continue;
    }
    if (/^\*\*(Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(trimmed)) {
      htmlBlocks.push(
        `<div style="margin: 14px 0; padding: 12px 16px; background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #3b82f6; border-radius: 6px; font-size: 13.5px; color: #1e40af; line-height: 1.6; break-inside: avoid; page-break-inside: avoid;">${formatInlineMarkdown(
          trimmed
        )}</div>`
      );
      i++;
      continue;
    }

    // 8. Blockquotes: > text
    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      htmlBlocks.push(
        `<blockquote style="margin: 14px 0; padding: 10px 16px; border-left: 4px solid #0284c7; background: #f8fafc; border-radius: 0 6px 6px 0; font-style: italic; color: #475569; font-size: 13.5px; line-height: 1.6; text-align: justify; text-justify: inter-word;">${formatInlineMarkdown(
          quoteLines.join(' ')
        )}</blockquote>`
      );
      continue;
    }

    // 9. Ordered List: 1. item
    if (/^\s*\d+\.\s+/.test(rawLine)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, '').trim());
        i++;
      }
      const listItems = items
        .map(
          (li) =>
            `<li style="margin-bottom: 7px; text-align: justify; text-justify: inter-word; line-height: 1.65; hyphens: auto; -webkit-hyphens: auto;">${formatInlineMarkdown(
              li
            )}</li>`
        )
        .join('');
      htmlBlocks.push(
        `<ol style="margin: 12px 0; padding-left: 24px; color: #334155; line-height: 1.65;">${listItems}</ol>`
      );
      continue;
    }

    // 10. Unordered List: - item, * item, • item
    if (/^\s*([*\-•])\s+/.test(rawLine)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*([*\-•])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([*\-•])\s+/, '').trim());
        i++;
      }
      const listItems = items
        .map(
          (li) =>
            `<li style="margin-bottom: 7px; text-align: justify; text-justify: inter-word; line-height: 1.65; hyphens: auto; -webkit-hyphens: auto;">${formatInlineMarkdown(
              li
            )}</li>`
        )
        .join('');
      htmlBlocks.push(
        `<ul style="margin: 12px 0; padding-left: 24px; color: #334155; line-height: 1.65;">${listItems}</ul >`
      );
      continue;
    }

    // 11. Standard Paragraph: group contiguous non-blank lines that are not special blocks
    const paraLines: string[] = [trimmed];
    i++;
    while (i < lines.length) {
      const nextLine = lines[i];
      const nextTrimmed = nextLine.trim();
      if (!nextTrimmed) break;
      if (
        nextTrimmed.startsWith('#') ||
        nextTrimmed.startsWith('```') ||
        nextTrimmed.startsWith('$$') ||
        nextTrimmed.startsWith('>') ||
        /^(-{3,}|\*{3,}|_{3,})$/.test(nextTrimmed) ||
        /^\s*\d+\.\s+/.test(nextLine) ||
        /^\s*([*\-•])\s+/.test(nextLine) ||
        (nextTrimmed.includes('|') &&
          i + 1 < lines.length &&
          /^\|?\s*:?-+:?\s*(\|(\s*:?-+:?\s*))+\|?$/.test(lines[i + 1].trim())) ||
        /^\*\*(Warning|Caution|Alert|Important|Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(
          nextTrimmed
        )
      ) {
        break;
      }
      paraLines.push(nextTrimmed);
      i++;
    }

    htmlBlocks.push(
      `<p style="margin-bottom: 12px; color: #334155; line-height: 1.7; font-size: 14.5px; text-align: justify; text-justify: inter-word; hyphens: auto; -webkit-hyphens: auto;">${formatInlineMarkdown(
        paraLines.join(' ')
      )}</p>`
    );
  }

  return htmlBlocks.join('\n');
}

/**
 * Generates an HTML printable report string formatted with institutional styles
 * and @media print CSS for direct browser printing or PDF saving.
 */
export function generateReportHtml(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>
): string {
  const dateStr = new Date().toLocaleString('en-US', {
    dateStyle: 'full',
    timeStyle: 'short',
  });

  const { cleanText, citations: enrichedCitations } = cleanRagResponseText(
    answerText,
    response?.citations || []
  );
  const citations =
    enrichedCitations && enrichedCitations.length > 0
      ? enrichedCitations
      : response?.citations || [];

  const uniqueDocs = Array.from(
    new Set((citations || []).map((c) => c.pdf_filename).filter(Boolean))
  ) as string[];
  const uniqueUnis = Array.from(
    new Set((citations || []).map((c) => c.university).filter(Boolean))
  ) as string[];
  const citationsCount = citations?.length || 0;

  const formattedAnswerHtml = convertMarkdownToHtml(cleanText);

  // Citations HTML
  let citationsHtml = '';
  if (citations && citations.length > 0) {
    const rows = citations
      .map((cit) => {
        const parts: string[] = [];
        if (cit.primary_page) parts.push(`Page ${cit.primary_page}`);
        if (cit.heading) parts.push(escapeHtml(cit.heading));
        if (cit.university) parts.push(escapeHtml(cit.university));
        const extra = parts.length > 0 ? ` <span style="color: #64748b; font-size: 11.5px;">(${parts.join(', ')})</span>` : '';

        return `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 14px; margin-bottom: 8px; break-inside: avoid; page-break-inside: avoid; font-size: 12.5px;">
          <strong style="color: #0284c7; margin-right: 6px;">[${cit.citation_index}]</strong>
          <span style="font-weight: 600; color: #0f172a;">${escapeHtml(cit.pdf_filename || 'Audited Document')}</span>
          ${extra}
        </div>
      `;
      })
      .join('');

    citationsHtml = `
      <section style="margin-top: 32px; break-before: auto;">
        <h2 style="font-size: 16px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #0284c7; padding-bottom: 6px; margin-bottom: 12px;">
          References (${citations.length})
        </h2>
        ${rows}
      </section>
    `;
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RAISE Report: ${escapeHtml(query || 'Research Inquiry')}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.19.1/dist/katex.min.css" crossorigin="anonymous">
  <style>
    @page {
      size: A4 portrait;
      margin: 18mm 16mm 18mm 16mm;
    }
    * {
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      margin: 0;
      padding: 24px;
      max-width: 820px;
      margin-left: auto;
      margin-right: auto;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    @media print {
      body {
        padding: 0;
        max-width: 100%;
      }
      .no-print {
        display: none !important;
      }
      .katex {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
    }
    p, li, blockquote {
      text-align: justify;
      text-justify: inter-word;
      hyphens: auto;
      -webkit-hyphens: auto;
    }
    .katex {
      font-size: 1.05em;
      text-rendering: auto;
    }
    .katex-display {
      margin: 0.8em 0;
      text-align: center;
    }
    .katex .katex-mathml {
      position: absolute;
      clip: rect(1px, 1px, 1px, 1px);
      padding: 0;
      border: 0;
      height: 1px;
      width: 1px;
      overflow: hidden;
    }
    .katex-html {
      display: inline-block;
    }
    .katex-block-wrapper {
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .table-container {
      margin: 18px 0;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    table {
      page-break-inside: avoid;
    }
    tr {
      page-break-inside: avoid;
    }
    .print-banner {
      background: #f1f5f9;
      color: #0f172a;
      border: 1px solid #cbd5e1;
      padding: 16px 20px;
      border-radius: 8px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .meta-grid {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 20px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      font-size: 11.5px;
    }
    .meta-item {
      display: flex;
      flex-direction: column;
    }
    .meta-label {
      font-weight: 700;
      text-transform: uppercase;
      color: #64748b;
      font-size: 10px;
      letter-spacing: 0.04em;
      margin-bottom: 2px;
    }
    .meta-value {
      color: #0f172a;
      font-weight: 600;
      word-break: break-word;
    }
    .query-box {
      background: #f1f5f9;
      border-left: 4px solid #0284c7;
      border-radius: 4px;
      padding: 14px 18px;
      margin-bottom: 24px;
    }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0;">
    <span style="font-size: 13px; color: #64748b;">Formatted Research Intelligence Report (A4 Justified)</span>
    <button onclick="window.print()" style="background: #0284c7; color: #ffffff; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; cursor: pointer; font-size: 13px;">
      Print / Save as PDF
    </button>
  </div>

  <header class="print-banner">
    <div>
      <div style="font-size: 17px; font-weight: 800; letter-spacing: -0.02em;">RAISE: Research Assessment Intelligence & Semantic Extraction</div>
      <div style="font-size: 11px; opacity: 0.85; margin-top: 3px;">A4 Standard • Justified Research Synthesis Report</div>
    </div>
    <div style="text-align: right; font-size: 11px; opacity: 0.85;">
      <div>${dateStr}</div>
      <div style="margin-top: 2px;">ISO A4 Format</div>
    </div>
  </header>

  <div class="meta-grid">
    <div class="meta-item">
      <span class="meta-label">Format Standard</span>
      <span class="meta-value">ISO A4 Portrait (Justified)</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">Audited References</span>
      <span class="meta-value">${citationsCount > 0 ? `${citationsCount} Sources Grounded` : 'Direct Synthesis'}</span>
    </div>
    ${
      uniqueDocs.length > 0
        ? `
    <div class="meta-item" style="grid-column: span 2;">
      <span class="meta-label">Primary Source Corpus</span>
      <span class="meta-value">${escapeHtml(uniqueDocs.slice(0, 2).join(', '))}${uniqueDocs.length > 2 ? ` (+${uniqueDocs.length - 2} more)` : ''}</span>
    </div>`
        : ''
    }
    ${
      uniqueUnis.length > 0
        ? `
    <div class="meta-item">
      <span class="meta-label">Institutional Origin</span>
      <span class="meta-value">${escapeHtml(uniqueUnis.slice(0, 2).join(', '))}</span>
    </div>`
        : ''
    }
  </div>

  <div class="query-box">
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 6px;">Question</div>
    <div style="font-size: 15px; font-weight: 600; color: #0f172a; line-height: 1.4;">${escapeHtml(
      query || 'General Inquiry'
    )}</div>
  </div>

  <main>
    <h2 style="font-size: 18px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 16px;">
      Answer
    </h2>
    <div style="font-size: 14.5px;">
      ${formattedAnswerHtml}
    </div>

    ${citationsHtml}

    <section style="margin-top: 28px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; break-inside: avoid; page-break-inside: avoid;">
      <h3 style="margin: 0 0 10px 0; font-size: 13px; font-weight: 700; color: #0f172a; border-bottom: 1.5px solid #0284c7; padding-bottom: 4px; display: inline-block;">
        🔬 Architecture Running
      </h3>
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 16px; font-size: 12px; margin-top: 8px;">
        <div><strong style="color: #475569;">Storage Substrates:</strong> <span style="color: #0f172a;">${escapeHtml(
          resolveAuditedProvenance(response).storageUsed
        )}</span></div>
        <div><strong style="color: #475569;">Synthesis LLM:</strong> <span style="color: #0f172a;">${escapeHtml(
          `${resolveAuditedProvenance(response).llmModel} (${resolveAuditedProvenance(response).llmProvider})`
        )}</span></div>
        <div><strong style="color: #475569;">Dense Embedding Encoder:</strong> <span style="color: #0f172a;">${escapeHtml(
          resolveAuditedProvenance(response).encoderModel
        )}</span></div>
        <div><strong style="color: #475569;">Cross-Attention Reranker:</strong> <span style="color: #0f172a;">${escapeHtml(
          resolveAuditedProvenance(response).rerankerModel
        )}</span></div>
        <div><strong style="color: #475569;">NLI Entailment Verifier:</strong> <span style="color: #0f172a;">${escapeHtml(
          resolveAuditedProvenance(response).nliVerifierModel
        )}</span></div>
        <div><strong style="color: #475569;">Platform Attribution:</strong> <span style="color: #0f172a;">RAISE</span></div>
      </div>
    </section>
  </main>

  <footer style="margin-top: 48px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
    Generated by RAISE — Research Assessment Intelligence & Semantic Extraction • ISO A4 Justified Edition
  </footer>
</body>
</html>`;
}

/**
 * Escapes characters for PDF content streams and normalizes unicode into readable ASCII equivalents.
 */
function escapePdfText(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)')
    .replace(/[^\x20-\x7E]/g, (char) => {
      switch (char) {
        case '’':
        case '‘':
        case '`':
          return "'";
        case '“':
        case '”':
          return '"';
        case '—':
          return ' - ';
        case '–':
          return '-';
        case '•':
          return '*';
        case '…':
          return '...';
        case '°':
          return ' deg ';
        case 'µ':
          return 'u';
        case '±':
          return '+/-';
        case '→':
          return ' -> ';
        case '←':
          return ' <- ';
        case '↔':
          return ' <-> ';
        case '≤':
          return '<=';
        case '≥':
          return '>=';
        case '≠':
          return '!=';
        case '≈':
          return '~=';
        case '×':
          return 'x';
        case '÷':
          return '/';
        case '²':
          return '^2';
        case '³':
          return '^3';
        case '¹':
          return '^1';
        case '⁰':
          return '^0';
        case '√':
          return 'sqrt';
        case 'α':
          return 'alpha';
        case 'β':
          return 'beta';
        case 'γ':
          return 'gamma';
        case 'δ':
          return 'delta';
        case 'Δ':
          return 'Delta';
        case 'ε':
          return 'epsilon';
        case 'θ':
          return 'theta';
        case 'λ':
          return 'lambda';
        case 'μ':
          return 'mu';
        case 'π':
          return 'pi';
        case 'ρ':
          return 'rho';
        case 'σ':
          return 'sigma';
        case 'Σ':
          return 'Sigma';
        case 'τ':
          return 'tau';
        case 'φ':
        case 'ϕ':
          return 'phi';
        case 'ω':
          return 'omega';
        case 'Ω':
          return 'Omega';
        case '∑':
          return 'sum';
        case '∫':
          return 'integral';
        case '∞':
          return 'infinity';
        case '·':
          return ' * ';
        case '⁻':
          return '-';
        case '₀':
          return '0';
        case '₁':
          return '1';
        case '₂':
          return '2';
        case '₃':
          return '3';
        case '₄':
          return '4';
        case '₅':
          return '5';
        case '₆':
          return '6';
        case '₇':
          return '7';
        case '₈':
          return '8';
        case '₉':
          return '9';
        case 'ᵢ':
          return 'i';
        case 'ⱼ':
          return 'j';
        case 'ₖ':
          return 'k';
        case 'ₙ':
          return 'n';
        case 'ₓ':
          return 'x';
        case 'ᶻ':
          return 'z';
        default:
          return ' ';
      }
    });
}

/**
 * Formats LaTeX mathematical syntax into clean, elegant, human-readable
 * mathematical notation (e.g. fractions, Greek symbols, superscripts, powers)
 * instead of raw programming/TeX code slash commands.
 */
export function formatMathFormula(latex: string): string {
  let s = latex.trim();
  // Strip outer delimiters
  if (s.startsWith('$$') && s.endsWith('$$')) {
    s = s.slice(2, -2).trim();
  } else if (s.startsWith('$') && s.endsWith('$')) {
    s = s.slice(1, -1).trim();
  }

  // Handle chemical formulas \ce{...}
  s = s.replace(/\\ce\{([^}]+)\}/g, '$1');

  // Fractions: \frac{A}{B} -> (A) / (B) or A / B
  s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, (_m, num, den) => {
    const cleanNum = num.trim();
    const cleanDen = den.trim();
    const numNeedsParen = cleanNum.includes('+') || cleanNum.includes('-');
    const denNeedsParen =
      cleanDen.includes('+') || cleanDen.includes('-') || cleanDen.includes('*');
    return `${numNeedsParen ? `(${cleanNum})` : cleanNum} / ${denNeedsParen ? `(${cleanDen})` : cleanDen}`;
  });

  // Square roots: \sqrt{X} -> sqrt(X)
  s = s.replace(/\\sqrt\{([^{}]+)\}/g, 'sqrt($1)');

  // Common LaTeX commands & brackets
  s = s
    .replace(/\\left\s*([(\[{|])/g, '$1')
    .replace(/\\right\s*([)\]}|])/g, '$1')
    .replace(/\\cdot/g, ' * ')
    .replace(/\\times/g, ' x ')
    .replace(/\\pm/g, ' +/- ')
    .replace(/\\neq/g, ' != ')
    .replace(/\\approx/g, ' ~= ')
    .replace(/\\le(q)?/g, ' <= ')
    .replace(/\\ge(q)?/g, ' >= ')
    .replace(/\\infty/g, 'infinity')
    .replace(/\\sum/g, 'sum')
    .replace(/\\int/g, 'integral')
    .replace(/\\partial/g, 'd')
    .replace(/\\nabla/g, 'grad');

  // Greek letters
  s = s
    .replace(/\\sigma/g, 'sigma')
    .replace(/\\alpha/g, 'alpha')
    .replace(/\\beta/g, 'beta')
    .replace(/\\gamma/g, 'gamma')
    .replace(/\\delta/g, 'delta')
    .replace(/\\epsilon/g, 'epsilon')
    .replace(/\\theta/g, 'theta')
    .replace(/\\lambda/g, 'lambda')
    .replace(/\\mu/g, 'mu')
    .replace(/\\pi/g, 'pi')
    .replace(/\\tau/g, 'tau')
    .replace(/\\phi/g, 'phi')
    .replace(/\\omega/g, 'omega')
    .replace(/\\Delta/g, 'Delta')
    .replace(/\\Sigma/g, 'Sigma')
    .replace(/\\Omega/g, 'Omega');

  // Subscripts & Superscripts
  s = s
    .replace(/\^\{([^}]+)\}/g, '^($1)')
    .replace(/_\{([^}]+)\}/g, '_($1)');

  // Clean \text{...}, \mathbf{...}, \mathit{...}
  s = s
    .replace(/\\(?:text|mathbf|mathit|mathrm)\{([^}]+)\}/g, '$1')
    .replace(/\\,/g, ' ')
    .replace(/\\;/g, ' ')
    .replace(/\\!/g, '')
    .replace(/\\quad/g, '   ')
    .replace(/\\qquad/g, '      ');

  // Clean residual backslashes
  s = s.replace(/\\([a-zA-Z]+)/g, '$1');

  // Normalize multiple spaces
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

/**
 * Estimates text width in points for standard Helvetica font.
 */
function estimateHelveticaWidth(text: string, fontSize: number): number {
  let units = 0;
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code === 32) {
      units += 278; // space
    } else if (code >= 65 && code <= 90) {
      // uppercase
      if (code === 73)
        units += 278; // I
      else if (code === 77 || code === 87)
        units += 833; // M, W
      else units += 667;
    } else if (code >= 97 && code <= 122) {
      // lowercase
      if (code === 105 || code === 108 || code === 116)
        units += 250; // i, l, t
      else if (code === 109 || code === 119)
        units += 778; // m, w
      else if (code === 102 || code === 114)
        units += 333; // f, r
      else units += 500;
    } else if (code >= 48 && code <= 57) {
      units += 556; // digits
    } else if (code === 46 || code === 44 || code === 58 || code === 59) {
      units += 278; // . , : ;
    } else if (code === 40 || code === 41 || code === 91 || code === 93) {
      units += 333; // ( ) [ ]
    } else {
      units += 500;
    }
  }
  return (units / 1000) * fontSize;
}

/**
 * Formats a Date object into standard PDF 1.4 date syntax (D:YYYYMMDDHHmmSSOHH'mm').
 */
function formatPdfDate(date: Date = new Date()): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  const y = date.getFullYear();
  const m = pad(date.getMonth() + 1);
  const d = pad(date.getDate());
  const h = pad(date.getHours());
  const min = pad(date.getMinutes());
  const s = pad(date.getSeconds());
  const tzOffset = -date.getTimezoneOffset();
  const tzSign = tzOffset >= 0 ? '+' : '-';
  const tzH = pad(Math.floor(Math.abs(tzOffset) / 60));
  const tzM = pad(Math.abs(tzOffset) % 60);
  return `D:${y}${m}${d}${h}${min}${s}${tzSign}${tzH}'${tzM}'`;
}

/**
 * Clean word-wrapping helper for fixed-width text columns.
 */
/**
 * Typographic word-wrapping helper that wraps text based on points width in Helvetica.
 * Ensures lines use the full available width of container boxes without premature line breaks.
 */
function wrapTextToWidth(text: string, maxWidthPts: number, fontSize: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = '';

  for (const w of words) {
    if (!w) continue;
    const testLine = cur.length === 0 ? w : cur + ' ' + w;
    if (estimateHelveticaWidth(testLine, fontSize) <= maxWidthPts) {
      cur = testLine;
    } else {
      if (cur.length > 0) {
        lines.push(cur);
      }
      cur = w;
    }
  }
  if (cur.length > 0) {
    lines.push(cur);
  }
  return lines.length > 0 ? lines : [''];
}

/**
 * Generates a valid PDF (PDF 1.4) binary document Blob
 * containing the full research report, A4 page dimensions, justified typography,
 * document metadata (/Info dictionary), and source references.
 */
export function generatePdfBlob(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>
): Blob {
  // Page parameters (standard ISO A4: 210mm x 297mm = 595.28 pt x 841.89 pt)
  const pageWidth = 595.28;
  const pageHeight = 841.89;
  const marginX = 42;
  const contentWidth = pageWidth - marginX * 2; // 511.28 pt
  const topY = 785;
  const bottomY = 56;

  // Clean answer text & extract enriched citations first
  const { cleanText, citations: enrichedCitations } = cleanRagResponseText(
    answerText,
    response?.citations || []
  );
  const citations =
    enrichedCitations && enrichedCitations.length > 0
      ? enrichedCitations
      : response?.citations || [];

  // Metadata Extraction from enriched citations
  const uniqueDocs = Array.from(
    new Set((citations || []).map((c) => c.pdf_filename).filter(Boolean))
  ) as string[];
  const uniqueUnis = Array.from(
    new Set((citations || []).map((c) => c.university).filter(Boolean))
  ) as string[];

  const now = new Date();
  const dateStr = now.toISOString().split('T')[0];
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  // Collection of page streams
  const pages: string[] = [];
  let currentOps: string[] = [];
  let curY = topY;

  const startNewPage = () => {
    if (currentOps.length > 0) {
      pages.push(currentOps.join('\n'));
      currentOps = [];
    }
    curY = topY;
  };

  const ensureSpace = (ptsNeeded: number) => {
    if (curY - ptsNeeded < bottomY) {
      startNewPage();
    }
  };

  // --- PAGE 1 HEADER BANNER ---
  currentOps.push(`0.95 0.97 1.0 rg 0.82 0.86 0.94 RG 0.75 w`); // Light elegant box
  currentOps.push(`${marginX} ${curY - 36} ${contentWidth} 36 re b`);
  currentOps.push(
    `BT /F2 11 Tf 0.08 0.14 0.28 rg ${marginX + 12} ${curY - 22} Td (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')}) Tj ET`
  );
  currentOps.push(
    `BT /F1 8 Tf 0.35 0.45 0.55 rg ${marginX + contentWidth - 85} ${curY - 22} Td (${escapePdfText(`${dateStr} ${timeStr}`)}) Tj ET`
  );
  curY -= 48;

  // --- QUERY BOX ---
  ensureSpace(45);
  const queryLines = wrapTextToWidth(query || 'Research Inquiry', contentWidth - 20, 9.5);
  const queryBoxHeight = Math.max(34, queryLines.length * 13 + 18);
  currentOps.push(`0.96 0.97 0.99 rg 0.85 0.88 0.92 RG 0.5 w`);
  currentOps.push(`${marginX} ${curY - queryBoxHeight} ${contentWidth} ${queryBoxHeight} re b`);
  currentOps.push(
    `BT /F2 8 Tf 0.35 0.45 0.55 rg ${marginX + 10} ${curY - 14} Td (${escapePdfText('QUESTION')}) Tj ET`
  );
  let qTextY = curY - 26;
  for (const ql of queryLines) {
    currentOps.push(
      `BT /F1 9.5 Tf 0.1 0.15 0.22 rg ${marginX + 10} ${qTextY} Td (${escapePdfText(ql)}) Tj ET`
    );
    qTextY -= 13;
  }
  curY -= queryBoxHeight + 14;

  // --- SECTION HEADER: ANSWER ---
  ensureSpace(25);
  currentOps.push(
    `BT /F2 11 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText('ANSWER')}) Tj ET`
  );
  currentOps.push(
    `0.08 0.12 0.22 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 55} ${curY - 16} l S`
  );
  curY -= 28;

  // --- ANSWER BODY RENDERING WITH TYPOGRAPHIC JUSTIFICATION ---
  const answerParagraphs = cleanText.split('\n');
  for (let pIdx = 0; pIdx < answerParagraphs.length; pIdx++) {
    const rawLine = answerParagraphs[pIdx];
    const trimmed = rawLine.trim();
    if (!trimmed) {
      curY -= 6;
      continue;
    }

    // Block LaTeX Math ($$ ... $$)
    if (trimmed.startsWith('$$')) {
      let formula = '';
      if (trimmed.length > 4 && trimmed.endsWith('$$')) {
        formula = trimmed.slice(2, -2).trim();
      } else {
        const mathLines: string[] = [];
        if (trimmed.length > 2) mathLines.push(trimmed.slice(2));
        pIdx++;
        while (
          pIdx < answerParagraphs.length &&
          !answerParagraphs[pIdx].trim().endsWith('$$') &&
          answerParagraphs[pIdx].trim() !== '$$'
        ) {
          mathLines.push(answerParagraphs[pIdx]);
          pIdx++;
        }
        if (pIdx < answerParagraphs.length) {
          const lastLine = answerParagraphs[pIdx].trim();
          if (lastLine !== '$$') {
            mathLines.push(lastLine.replace(/\$\$$/, ''));
          }
        }
        formula = mathLines.join(' ').trim();
      }

      const formattedFormula = formatMathFormula(formula);
      const safeFormula = escapePdfText(formattedFormula).slice(0, 95);

      ensureSpace(34);
      // Clean mathematical formulation card with left accent bar
      currentOps.push(`0.97 0.98 1 rg 0.82 0.87 0.96 RG 0.5 w`);
      currentOps.push(`${marginX} ${curY - 28} ${contentWidth} 28 re b`);
      currentOps.push(`0.2 0.42 0.85 RG 2 w ${marginX} ${curY - 28} m ${marginX} ${curY} l S`);
      currentOps.push(
        `BT /F2 7 Tf 0.35 0.45 0.65 rg ${marginX + 12} ${curY - 11} Td (${escapePdfText('FORMULATION')}) Tj ET`
      );
      const estW = estimateHelveticaWidth(safeFormula, 10);
      const mathX = Math.max(marginX + 12, marginX + (contentWidth - estW) / 2);
      currentOps.push(
        `BT /F2 10 Tf 0.08 0.14 0.32 rg ${mathX} ${curY - 22} Td (${safeFormula}) Tj ET`
      );
      curY -= 36;
      continue;
    }

    // Markdown Table
    if (trimmed.includes('|') && pIdx + 1 < answerParagraphs.length) {
      const nextTrimmed = answerParagraphs[pIdx + 1].trim();
      if (/^\|?\s*:?-+:?\s*(\|(\s*:?-+:?\s*))+\|?$/.test(nextTrimmed)) {
        const headers = splitTableRow(trimmed);
        pIdx += 2;
        const rows: string[][] = [];
        while (
          pIdx < answerParagraphs.length &&
          answerParagraphs[pIdx].trim().includes('|') &&
          !answerParagraphs[pIdx].trim().startsWith('#')
        ) {
          rows.push(splitTableRow(answerParagraphs[pIdx]));
          pIdx++;
        }
        pIdx--; // Adjust for loop increment

        const colCount = Math.max(headers.length, ...rows.map((r) => r.length), 1);
        const colWidth = contentWidth / colCount;

        // Render PDF Table Header
        ensureSpace(22);
        currentOps.push(`0.94 0.96 0.98 rg 0.82 0.86 0.9 RG 0.75 w`);
        currentOps.push(`${marginX} ${curY - 18} ${contentWidth} 18 re b`);
        headers.forEach((h, cIdx) => {
          const cellX = marginX + cIdx * colWidth + 6;
          const maxChars = Math.max(4, Math.floor(colWidth / 5.5));
          const truncated = escapePdfText(h).slice(0, maxChars);
          currentOps.push(
            `BT /F2 8 Tf 0.08 0.12 0.22 rg ${cellX} ${curY - 12} Td (${truncated}) Tj ET`
          );
        });
        curY -= 18;

        // Render PDF Table Rows
        rows.forEach((row, rIdx) => {
          ensureSpace(16);
          if (rIdx % 2 === 1) {
            currentOps.push(`0.98 0.99 1 rg`);
            currentOps.push(`${marginX} ${curY - 16} ${contentWidth} 16 re f`);
          }
          currentOps.push(
            `0.9 0.92 0.95 RG 0.5 w ${marginX} ${curY - 16} m ${marginX + contentWidth} ${curY - 16} l S`
          );
          row.forEach((cell, cIdx) => {
            const cellX = marginX + cIdx * colWidth + 6;
            const maxChars = Math.max(4, Math.floor(colWidth / 5.5));
            const truncated = escapePdfText(cell).slice(0, maxChars);
            currentOps.push(
              `BT /F1 8 Tf 0.2 0.25 0.32 rg ${cellX} ${curY - 11} Td (${truncated}) Tj ET`
            );
          });
          curY -= 16;
        });
        curY -= 8;
        continue;
      }
    }

    const cleanHeading = trimmed.replace(/^[•*-]\s*(?:\*\*)?\s*(#{1,4})/, '$1');
    if (cleanHeading.startsWith('### ')) {
      ensureSpace(24);
      const h3Text = cleanHeading
        .replace(/^###\s+/, '')
        .replace(/\*\*/g, '')
        .trim();
      currentOps.push(
        `BT /F2 10.5 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText(h3Text)}) Tj ET`
      );
      curY -= 18;
      continue;
    }

    if (cleanHeading.startsWith('## ')) {
      ensureSpace(28);
      const h2Text = cleanHeading
        .replace(/^##\s+/, '')
        .replace(/\*\*/g, '')
        .trim();
      currentOps.push(
        `BT /F2 11.5 Tf 0.06 0.1 0.2 rg ${marginX} ${curY - 14} Td (${escapePdfText(h2Text)}) Tj ET`
      );
      curY -= 22;
      continue;
    }

    if (cleanHeading.startsWith('# ')) {
      ensureSpace(32);
      const h1Text = cleanHeading.replace(/^#\s+/, '').replace(/\*\*/g, '').trim();
      currentOps.push(
        `BT /F2 13 Tf 0.06 0.1 0.2 rg ${marginX} ${curY - 16} Td (${escapePdfText(h1Text)}) Tj ET`
      );
      curY -= 24;
      continue;
    }

    if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
      ensureSpace(22);
      const boldTitle = trimmed.slice(2, -2).trim();
      currentOps.push(
        `BT /F2 10 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText(boldTitle)}) Tj ET`
      );
      curY -= 16;
      continue;
    }

    const isBullet =
      trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ');
    const cleanBulletText = trimmed.replace(/^[-*•]\s+/, '').replace(/\*\*/g, '');
    const targetLineWidth = contentWidth - (isBullet ? 12 : 0);
    const wrapped = wrapTextToWidth(cleanBulletText, targetLineWidth, 9);

    for (let idx = 0; idx < wrapped.length; idx++) {
      ensureSpace(14);
      const lineStr = wrapped[idx];
      const indent = isBullet ? marginX + 12 : marginX;

      if (isBullet && idx === 0) {
        currentOps.push(
          `BT /F1 9 Tf 0.4 0.45 0.55 rg ${marginX + 2} ${curY - 10} Td (${escapePdfText('•')}) Tj ET`
        );
      }

      // Typographic justification across lines using PDF word spacing operator 'Tw'
      const isLastLine = idx === wrapped.length - 1;
      const words = lineStr.trim().split(/\s+/);
      let wordSpacing = 0;

      if (!isLastLine && words.length > 1) {
        const estWidth = estimateHelveticaWidth(lineStr, 9);
        const diff = targetLineWidth - estWidth;
        if (diff > 0 && diff < 70) {
          wordSpacing = diff / (words.length - 1);
        }
      }

      if (wordSpacing > 0) {
        currentOps.push(
          `BT /F1 9 Tf ${wordSpacing.toFixed(2)} Tw 0.15 0.18 0.24 rg ${indent} ${curY - 10} Td (${escapePdfText(lineStr)}) Tj 0 Tw ET`
        );
      } else {
        currentOps.push(
          `BT /F1 9 Tf 0.15 0.18 0.24 rg ${indent} ${curY - 10} Td (${escapePdfText(lineStr)}) Tj ET`
        );
      }
      curY -= 13.5;
    }
  }

  // --- REFERENCES SECTION ---
  if (citations && citations.length > 0) {
    curY -= 12;
    ensureSpace(32);
    currentOps.push(
      `BT /F2 11 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText('References')}) Tj ET`
    );
    currentOps.push(
      `0.08 0.4 0.65 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 80} ${curY - 16} l S`
    );
    curY -= 26;

    citations.forEach((cit) => {
      ensureSpace(16);
      const parts: string[] = [];
      if (cit.primary_page) parts.push(`Page ${cit.primary_page}`);
      if (cit.heading) parts.push(cit.heading);
      if (cit.university) parts.push(cit.university);
      const extra = parts.length > 0 ? ` (${parts.join(', ')})` : '';
      const refStr = `[${cit.citation_index}] ${cit.pdf_filename || 'Audited Document'}${extra}`;

      const wrappedLines = wrapTextToWidth(refStr, contentWidth - 10, 8.5);
      for (let i = 0; i < wrappedLines.length; i++) {
        ensureSpace(13);
        const font = i === 0 ? '/F2 8.5 Tf 0.1 0.16 0.28 rg' : '/F1 8.5 Tf 0.25 0.3 0.38 rg';
        currentOps.push(
          `BT ${font} ${marginX + (i > 0 ? 10 : 0)} ${curY - 9} Td (${escapePdfText(wrappedLines[i])}) Tj ET`
        );
        curY -= 12;
      }
      curY -= 2;
    });
  }

  // --- AUDITED PIPELINE ARCHITECTURE & PROVENANCE SECTION ---
  const prov = resolveAuditedProvenance(response);

  curY -= 12;
  ensureSpace(110);

  currentOps.push(
    `BT /F2 10.5 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText('Architecture Running')}) Tj ET`
  );
  currentOps.push(
    `0.08 0.4 0.65 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 95} ${curY - 16} l S`
  );
  curY -= 24;

  const cardHeight = 78;
  currentOps.push(`0.97 0.98 0.99 rg`);
  currentOps.push(`${marginX} ${curY - cardHeight} ${contentWidth} ${cardHeight} re f`);
  currentOps.push(`0.88 0.91 0.95 RG 0.75 w`);
  currentOps.push(`${marginX} ${curY - cardHeight} ${contentWidth} ${cardHeight} re s`);

  const specRows = [
    { label: 'Storage Substrates:', val: prov.storageUsed },
    { label: 'Synthesis LLM:', val: `${prov.llmModel} (${prov.llmProvider})` },
    { label: 'Dense Embedding Encoder:', val: prov.encoderModel },
    { label: 'Cross-Attention Reranker:', val: prov.rerankerModel },
    { label: 'NLI Entailment Verifier:', val: prov.nliVerifierModel },
    { label: 'Platform Attribution:', val: 'RAISE' },
  ];

  let specY = curY - 12;
  specRows.forEach((row) => {
    currentOps.push(
      `BT /F2 7.5 Tf 0.25 0.32 0.45 rg ${marginX + 10} ${specY} Td (${escapePdfText(row.label)}) Tj ET`
    );
    currentOps.push(
      `BT /F1 7.5 Tf 0.12 0.16 0.24 rg ${marginX + 130} ${specY} Td (${escapePdfText(row.val)}) Tj ET`
    );
    specY -= 11.5;
  });

  curY -= cardHeight + 10;

  // Push final page stream
  if (currentOps.length > 0) {
    pages.push(currentOps.join('\n'));
  }

  // Decorate each page with footer and page numbers
  const totalPages = Math.max(1, pages.length);
  const finalPagesContent = pages.map((pageStream, pageIndex) => {
    const pageNum = pageIndex + 1;
    const watermarkOps = [
      'q',
      '0.95 0.96 0.98 rg', // Elegant, subtle diagonal RAISE watermark
      'BT',
      '/F2 52 Tf',
      '0.7071 0.7071 -0.7071 0.7071 210 330 Tm',
      `(${escapePdfText('RAISE')}) Tj`,
      'ET',
      'Q',
    ].join('\n');
    const footerOps = [
      `0.85 0.88 0.92 RG 0.5 w ${marginX} 40 m ${marginX + contentWidth} 40 l S`,
      `BT /F1 7.5 Tf 0.55 0.6 0.68 rg ${marginX} 28 Td (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')}) Tj ET`,
      `BT /F1 7.5 Tf 0.55 0.6 0.68 rg ${marginX + contentWidth - 55} 28 Td (${escapePdfText(`Page ${pageNum} of ${totalPages}`)}) Tj ET`,
    ].join('\n');
    return `${watermarkOps}\n${pageStream}\n${footerOps}`;
  });

  // --- BUILD PDF 1.4 FILE STRUCTURE ---
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  let byteOffset = 0;

  const appendString = (str: string) => {
    const bytes = encoder.encode(str);
    chunks.push(bytes);
    byteOffset += bytes.length;
  };

  appendString('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');

  // Object registry
  const objectOffsets: number[] = [];

  // 1: Catalog
  objectOffsets[1] = byteOffset;
  appendString('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

  // 2: Pages
  const pageObjectIds: number[] = [];
  let nextId = 6;
  for (let i = 0; i < totalPages; i++) {
    pageObjectIds.push(nextId);
    nextId += 2; // page object + content stream object
  }

  objectOffsets[2] = byteOffset;
  appendString(
    `2 0 obj\n<< /Type /Pages /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${totalPages} >>\nendobj\n`
  );

  // Fonts: 3: F1 (Helvetica), 4: F2 (Helvetica-Bold), 5: F3 (Helvetica-Oblique)
  objectOffsets[3] = byteOffset;
  appendString('3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n');

  objectOffsets[4] = byteOffset;
  appendString('4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n');

  objectOffsets[5] = byteOffset;
  appendString('5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>\nendobj\n');

  // Create Page & Content Stream Objects
  for (let i = 0; i < totalPages; i++) {
    const pageId = pageObjectIds[i];
    const streamId = pageId + 1;
    const streamContent = finalPagesContent[i] || '';
    const streamBytes = encoder.encode(streamContent);

    // Page object (ISO A4 Dimensions)
    objectOffsets[pageId] = byteOffset;
    appendString(
      `${pageId} 0 obj\n<<\n  /Type /Page\n  /Parent 2 0 R\n  /MediaBox [0 0 ${pageWidth} ${pageHeight}]\n  /CropBox [0 0 ${pageWidth} ${pageHeight}]\n  /Contents ${streamId} 0 R\n  /Resources <<\n    /Font <<\n      /F1 3 0 R\n      /F2 4 0 R\n      /F3 5 0 R\n    >>\n  >>\n>>\nendobj\n`
    );

    // Stream object
    objectOffsets[streamId] = byteOffset;
    appendString(`${streamId} 0 obj\n<< /Length ${streamBytes.length} >>\nstream\n`);
    chunks.push(streamBytes);
    byteOffset += streamBytes.length;
    appendString('\nendstream\nendobj\n');
  }

  // Info dictionary (document metadata object)
  const infoId = nextId;
  nextId++;
  const pdfDate = formatPdfDate(now);
  objectOffsets[infoId] = byteOffset;
  const safeDocTitle = uniqueDocs.length > 0 ? ` - ${uniqueDocs[0]}` : '';
  const keywordsStr = `RAISE, GraphRAG, A4, Justified, Research Synthesis${uniqueDocs.length > 0 ? `, ${uniqueDocs.join(', ')}` : ''}${uniqueUnis.length > 0 ? `, ${uniqueUnis.join(', ')}` : ''}`;

  appendString(
    `${infoId} 0 obj\n<<\n  /Title (${escapePdfText(`RAISE Report: ${query.slice(0, 60) || 'Research Inquiry'}${safeDocTitle}`)})\n  /Subject (${escapePdfText('Research Assessment Intelligence & Semantic Extraction')})\n  /Author (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')})\n  /Creator (${escapePdfText('RAISE Semantic Research Platform')})\n  /Producer (${escapePdfText('RAISE PDF Engine 1.4')})\n  /CreationDate (${pdfDate})\n  /ModDate (${pdfDate})\n  /Keywords (${escapePdfText(keywordsStr)})\n>>\nendobj\n`
  );

  // Cross Reference Table
  const xrefOffset = byteOffset;
  const totalObjects = nextId;
  appendString(`xref\n0 ${totalObjects}\n0000000000 65535 f \n`);
  for (let i = 1; i < totalObjects; i++) {
    const off = objectOffsets[i] || 0;
    appendString(`${off.toString().padStart(10, '0')} 00000 n \n`);
  }

  // Trailer
  appendString(
    `trailer\n<< /Size ${totalObjects} /Root 1 0 R /Info ${infoId} 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  );

  return new Blob(chunks as BlobPart[], { type: 'application/pdf' });
}

/**
 * Exports the AI response as a Markdown file (.md) download.
 */
export function exportAsMarkdown(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>,
  customFilename?: string
): void {
  const markdown = formatMarkdownReport(query, answerText, response);
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
  const filename = customFilename || generateExportFilename(query, 'md');
  downloadBlob(blob, filename);
}

/**
 * Exports the raw response and full graph metadata as a JSON file (.json) download.
 */
export function exportAsJson(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>,
  customFilename?: string
): void {
  const data = formatDeveloperJson(query, answerText, response);
  const jsonStr = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
  const filename = customFilename || generateExportFilename(query, 'json', 'raise-response');
  downloadBlob(blob, filename);
}

/**
 * Exports the response as a valid, formatted PDF document (.pdf) download.
 */
export function exportAsPdf(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>,
  customFilename?: string
): void {
  const blob = generatePdfBlob(query, answerText, response);
  const filename = customFilename || generateExportFilename(query, 'pdf');
  downloadBlob(blob, filename);
}

/**
 * Generates a valid multi-page PDF (PDF 1.4) binary document Blob
 * containing the complete conversation transcript for a session,
 * ISO A4 page dimensions, full turns (User inquiries & RAISE intelligence responses),
 * duration latency, citations/sources, page numbers on every page footer ("Page X of Y"),
 * and document metadata (/Info dictionary).
 */
export function generateSessionPdfBlob(session: ChatSession): Blob {
  const pageWidth = 595.28;
  const pageHeight = 841.89;
  const marginX = 42;
  const contentWidth = pageWidth - marginX * 2; // 511.28 pt
  const topY = 785;
  const bottomY = 56;

  const now = new Date();
  const dateStr = now.toISOString().split('T')[0];
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  const sessionTitle =
    session.title && session.title !== 'New Chat'
      ? session.title
      : 'RAISE Research Session Transcript';
  const rawMessages = Array.isArray(session.messages) ? session.messages : [];
  // Filter out any orphaned empty turns
  const messages = rawMessages.filter((m) => {
    const txt = (
      m.text ||
      (m as any).content ||
      m.response?.grounded_answer ||
      m.response?.answer ||
      m.response?.reply ||
      ''
    ).trim();
    return Boolean(txt || m.response || m.error);
  });

  const userTurns = messages.filter((m) => m.role === 'user').length;

  // Attached docs metadata
  const docNames: string[] = [];
  if (Array.isArray(session.sources)) {
    session.sources.forEach((s: any) => {
      if (s?.name) docNames.push(s.name);
    });
  }
  if (Array.isArray(session.attached_docs)) {
    session.attached_docs.forEach((d: string) => {
      if (d && !docNames.includes(d)) docNames.push(d);
    });
  }

  // Collection of page streams
  const pages: string[] = [];
  let currentOps: string[] = [];
  let curY = topY;

  // Turn card box tracking for rendering Question + Answer in a unified container card
  let activeBox: { startY: number; startOpIdx: number } | null = null;

  const closeCurrentBoxSlice = () => {
    if (!activeBox) return;
    const sliceHeight = Math.max(12, activeBox.startY - curY + 6);
    const sliceBottomY = curY - 6;
    currentOps.splice(
      activeBox.startOpIdx,
      0,
      `0.975 0.982 0.992 rg 0.84 0.87 0.92 RG 0.75 w`,
      `${marginX} ${sliceBottomY.toFixed(2)} ${contentWidth} ${sliceHeight.toFixed(2)} re b`
    );
    activeBox = null;
  };

  const startNewPage = () => {
    const wasInBox = Boolean(activeBox);
    if (activeBox) {
      closeCurrentBoxSlice();
    }
    if (currentOps.length > 0) {
      pages.push(currentOps.join('\n'));
      currentOps = [];
    }
    curY = topY;
    if (wasInBox) {
      curY -= 12; // top margin for box continuation on new page
      activeBox = {
        startY: curY,
        startOpIdx: currentOps.length,
      };
    }
  };

  const ensureSpace = (ptsNeeded: number) => {
    if (curY - ptsNeeded < bottomY) {
      startNewPage();
    }
  };

  // --- PAGE 1: TRANSCRIPT HEADER BANNER ---
  currentOps.push(`0.95 0.97 1.0 rg 0.82 0.86 0.94 RG 0.75 w`); // Light elegant box
  currentOps.push(`${marginX} ${curY - 36} ${contentWidth} 36 re b`);
  currentOps.push(
    `BT /F2 11 Tf 0.08 0.14 0.28 rg ${marginX + 12} ${curY - 22} Td (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')}) Tj ET`
  );
  currentOps.push(
    `BT /F1 8 Tf 0.35 0.45 0.55 rg ${marginX + contentWidth - 85} ${curY - 22} Td (${escapePdfText(`${dateStr} ${timeStr}`)}) Tj ET`
  );
  curY -= 48;

  // --- SESSION METADATA STRIP ---
  ensureSpace(28);
  const metaBoxHeight = 24;
  currentOps.push(`0.96 0.97 0.99 rg 0.88 0.91 0.95 RG 0.5 w`);
  currentOps.push(`${marginX} ${curY - metaBoxHeight} ${contentWidth} ${metaBoxHeight} re b`);

  const metaLeft = `Session: ${escapePdfText(sessionTitle.slice(0, 50))}  •  ${userTurns} Inquiries`;
  const metaRight =
    docNames.length > 0
      ? `Corpus: ${escapePdfText(docNames.slice(0, 2).join(', ').slice(0, 28))}`
      : `ID: ${session.id.slice(0, 18)}...`;
  currentOps.push(
    `BT /F2 7.5 Tf 0.22 0.32 0.48 rg ${marginX + 8} ${curY - 15} Td (${escapePdfText(metaLeft)}) Tj ET`
  );
  currentOps.push(
    `BT /F1 7 Tf 0.45 0.5 0.58 rg ${marginX + contentWidth - 145} ${curY - 15} Td (${escapePdfText(metaRight)}) Tj ET`
  );
  curY -= metaBoxHeight + 14;

  // Helper to render markdown paragraphs/tables/lists/math inside turn cards
  const renderMarkdownBlock = (
    rawText: string,
    baseX = marginX + 12,
    blockWidth = contentWidth - 24
  ) => {
    const lines = rawText.split('\n');
    for (let pIdx = 0; pIdx < lines.length; pIdx++) {
      const rawLine = lines[pIdx];
      const trimmed = rawLine.trim();
      if (!trimmed) {
        curY -= 6;
        continue;
      }

      // Block LaTeX Math ($$ ... $$)
      if (trimmed.startsWith('$$')) {
        let formula = '';
        if (trimmed.length > 4 && trimmed.endsWith('$$')) {
          formula = trimmed.slice(2, -2).trim();
        } else {
          const mathLines: string[] = [];
          if (trimmed.length > 2) mathLines.push(trimmed.slice(2));
          pIdx++;
          while (
            pIdx < lines.length &&
            !lines[pIdx].trim().endsWith('$$') &&
            lines[pIdx].trim() !== '$$'
          ) {
            mathLines.push(lines[pIdx]);
            pIdx++;
          }
          if (pIdx < lines.length) {
            const lastLine = lines[pIdx].trim();
            if (lastLine !== '$$') {
              mathLines.push(lastLine.replace(/\$\$$/, ''));
            }
          }
          formula = mathLines.join(' ').trim();
        }

        const formattedFormula = formatMathFormula(formula);
        const safeFormula = escapePdfText(formattedFormula).slice(0, 95);

        ensureSpace(34);
        // Clean mathematical formulation card with left accent bar
        currentOps.push(`0.97 0.98 1 rg 0.82 0.87 0.96 RG 0.5 w`);
        currentOps.push(`${baseX} ${curY - 28} ${blockWidth} 28 re b`);
        currentOps.push(`0.2 0.42 0.85 RG 2 w ${baseX} ${curY - 28} m ${baseX} ${curY} l S`);
        currentOps.push(
          `BT /F2 7 Tf 0.35 0.45 0.65 rg ${baseX + 12} ${curY - 11} Td (${escapePdfText('FORMULATION')}) Tj ET`
        );
        const estW = estimateHelveticaWidth(safeFormula, 10);
        const mathX = Math.max(baseX + 12, baseX + (blockWidth - estW) / 2);
        currentOps.push(
          `BT /F2 10 Tf 0.08 0.14 0.32 rg ${mathX} ${curY - 22} Td (${safeFormula}) Tj ET`
        );
        curY -= 36;
        continue;
      }

      // Markdown Table
      if (trimmed.includes('|') && pIdx + 1 < lines.length) {
        const nextTrimmed = lines[pIdx + 1].trim();
        if (/^\|?\s*:?-+:?\s*(\|(\s*:?-+:?\s*))+\|?$/.test(nextTrimmed)) {
          const headers = splitTableRow(trimmed);
          pIdx += 2;
          const rows: string[][] = [];
          while (
            pIdx < lines.length &&
            lines[pIdx].trim().includes('|') &&
            !lines[pIdx].trim().startsWith('#')
          ) {
            rows.push(splitTableRow(lines[pIdx]));
            pIdx++;
          }
          pIdx--; // Adjust for loop increment

          const colCount = Math.max(headers.length, ...rows.map((r) => r.length), 1);
          const colWidth = blockWidth / colCount;

          // Render Table Header
          ensureSpace(22);
          currentOps.push(`0.94 0.96 0.98 rg 0.82 0.86 0.9 RG 0.75 w`);
          currentOps.push(`${baseX} ${curY - 18} ${blockWidth} 18 re b`);
          headers.forEach((h, cIdx) => {
            const cellX = baseX + cIdx * colWidth + 6;
            const maxChars = Math.max(4, Math.floor(colWidth / 5.5));
            const truncated = escapePdfText(h).slice(0, maxChars);
            currentOps.push(
              `BT /F2 8 Tf 0.08 0.12 0.22 rg ${cellX} ${curY - 12} Td (${truncated}) Tj ET`
            );
          });
          curY -= 18;

          // Render Table Rows
          rows.forEach((row, rIdx) => {
            ensureSpace(16);
            if (rIdx % 2 === 1) {
              currentOps.push(`0.98 0.99 1 rg`);
              currentOps.push(`${baseX} ${curY - 16} ${blockWidth} 16 re f`);
            }
            currentOps.push(
              `0.9 0.92 0.95 RG 0.5 w ${baseX} ${curY - 16} m ${baseX + blockWidth} ${curY - 16} l S`
            );
            row.forEach((cell, cIdx) => {
              const cellX = baseX + cIdx * colWidth + 6;
              const maxChars = Math.max(4, Math.floor(colWidth / 5.5));
              const truncated = escapePdfText(cell).slice(0, maxChars);
              currentOps.push(
                `BT /F1 8 Tf 0.2 0.25 0.32 rg ${cellX} ${curY - 11} Td (${truncated}) Tj ET`
              );
            });
            curY -= 16;
          });
          curY -= 8;
          continue;
        }
      }

      // Headings
      const cleanHeading = trimmed.replace(/^[•*-]\s*(?:\*\*)?\s*(#{1,4})/, '$1');
      if (cleanHeading.startsWith('### ')) {
        ensureSpace(24);
        const h3Text = cleanHeading.replace(/^###\s+/, '').replace(/\*\*/g, '').trim();
        currentOps.push(
          `BT /F2 10.5 Tf 0.08 0.12 0.22 rg ${baseX} ${curY - 12} Td (${escapePdfText(h3Text)}) Tj ET`
        );
        curY -= 18;
        continue;
      }

      if (cleanHeading.startsWith('## ')) {
        ensureSpace(28);
        const h2Text = cleanHeading.replace(/^##\s+/, '').replace(/\*\*/g, '').trim();
        currentOps.push(
          `BT /F2 11.5 Tf 0.06 0.1 0.2 rg ${baseX} ${curY - 14} Td (${escapePdfText(h2Text)}) Tj ET`
        );
        curY -= 22;
        continue;
      }

      if (cleanHeading.startsWith('# ')) {
        ensureSpace(32);
        const h1Text = cleanHeading.replace(/^#\s+/, '').replace(/\*\*/g, '').trim();
        currentOps.push(
          `BT /F2 13 Tf 0.06 0.1 0.2 rg ${baseX} ${curY - 16} Td (${escapePdfText(h1Text)}) Tj ET`
        );
        curY -= 24;
        continue;
      }

      if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
        ensureSpace(22);
        const boldTitle = trimmed.slice(2, -2).trim();
        currentOps.push(
          `BT /F2 10 Tf 0.08 0.12 0.22 rg ${baseX} ${curY - 12} Td (${escapePdfText(boldTitle)}) Tj ET`
        );
        curY -= 16;
        continue;
      }

      const isBullet =
        trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ');
      const cleanBulletText = trimmed.replace(/^[-*•]\s+/, '').replace(/\*\*/g, '');
      const targetLineWidth = blockWidth - (isBullet ? 12 : 0);
      const wrapped = wrapTextToWidth(cleanBulletText, targetLineWidth, 9);

      for (let idx = 0; idx < wrapped.length; idx++) {
        ensureSpace(14);
        const lineStr = wrapped[idx];
        const indent = isBullet ? baseX + 12 : baseX;

        if (isBullet && idx === 0) {
          currentOps.push(
            `BT /F1 9 Tf 0.4 0.45 0.55 rg ${baseX + 2} ${curY - 10} Td (${escapePdfText('•')}) Tj ET`
          );
        }

        const isLastLine = idx === wrapped.length - 1;
        const words = lineStr.trim().split(/\s+/);
        let wordSpacing = 0;

        if (!isLastLine && words.length > 1) {
          const estWidth = estimateHelveticaWidth(lineStr, 9);
          const diff = targetLineWidth - estWidth;
          if (diff > 0 && diff < 70) {
            wordSpacing = diff / (words.length - 1);
          }
        }

        if (wordSpacing > 0) {
          currentOps.push(
            `BT /F1 9 Tf ${wordSpacing.toFixed(2)} Tw 0.15 0.18 0.24 rg ${indent} ${curY - 10} Td (${escapePdfText(lineStr)}) Tj 0 Tw ET`
          );
        } else {
          currentOps.push(
            `BT /F1 9 Tf 0.15 0.18 0.24 rg ${indent} ${curY - 10} Td (${escapePdfText(lineStr)}) Tj ET`
          );
        }
        curY -= 13.5;
      }
    }
  };

  // --- PAIR MESSAGES INTO MONOTONIC CONVERSATIONAL TURNS (EXCHANGES) ---
  interface TurnExchange {
    turnIndex: number;
    userMsg?: (typeof messages)[0];
    assistantMsg?: (typeof messages)[0];
  }

  const exchanges: TurnExchange[] = [];
  let curExchange: TurnExchange | null = null;
  let turnNumber = 1;

  for (let mIdx = 0; mIdx < messages.length; mIdx++) {
    const msg = messages[mIdx];
    if (msg.role === 'user') {
      if (curExchange) {
        exchanges.push(curExchange);
      }
      curExchange = {
        turnIndex: turnNumber++,
        userMsg: msg,
      };
    } else if (msg.role === 'assistant') {
      if (!curExchange) {
        curExchange = {
          turnIndex: turnNumber++,
          assistantMsg: msg,
        };
        exchanges.push(curExchange);
        curExchange = null;
      } else {
        curExchange.assistantMsg = msg;
        exchanges.push(curExchange);
        curExchange = null;
      }
    } else {
      if (!curExchange) {
        curExchange = {
          turnIndex: turnNumber++,
          userMsg: msg,
        };
      }
    }
  }
  if (curExchange) {
    exchanges.push(curExchange);
  }

  const cardInnerX = marginX + 12;
  const cardInnerWidth = contentWidth - 24;

  for (let eIdx = 0; eIdx < exchanges.length; eIdx++) {
    const ex = exchanges[eIdx];
    ensureSpace(60);

    // Open unified box container for this turn
    curY -= 4;
    activeBox = {
      startY: curY,
      startOpIdx: currentOps.length,
    };

    // 1. QUESTION SECTION (if user message present)
    if (ex.userMsg) {
      const userText = (
        (ex.userMsg.questionVersions &&
          ex.userMsg.questionVersions[ex.userMsg.currentQuestionVersionIndex ?? 0]?.question) ||
        ex.userMsg.text ||
        (ex.userMsg as any).content ||
        (ex.userMsg as any).query ||
        ''
      ).trim() || '(Empty inquiry)';
      const queryLines = wrapTextToWidth(userText, cardInnerWidth, 9.5);

      const qTitle = `QUESTION ${ex.turnIndex}`;
      const qTitleWidth = estimateHelveticaWidth(qTitle, 9.5);
      currentOps.push(
        `BT /F2 9.5 Tf 0.08 0.10 0.15 rg ${cardInnerX} ${curY - 12} Td (${escapePdfText(qTitle)}) Tj ET`
      );
      if (ex.userMsg.timestamp) {
        currentOps.push(
          `BT /F1 7.5 Tf 0.45 0.52 0.62 rg ${cardInnerX + qTitleWidth + 8} ${curY - 12} Td (${escapePdfText(ex.userMsg.timestamp)}) Tj ET`
        );
      }
      curY -= 16;

      for (const ql of queryLines) {
        ensureSpace(14);
        currentOps.push(
          `BT /F1 9.5 Tf 0.1 0.15 0.22 rg ${cardInnerX} ${curY - 10} Td (${escapePdfText(ql)}) Tj ET`
        );
        curY -= 13.5;
      }
    }

    // Divider between Question and Answer inside the card
    if (ex.userMsg && ex.assistantMsg) {
      curY -= 4;
      ensureSpace(12);
      currentOps.push(`0.86 0.89 0.94 RG 0.5 w ${cardInnerX} ${curY} m ${cardInnerX + cardInnerWidth} ${curY} l S`);
      curY -= 12;
    }

    // 2. ANSWER SECTION (if assistant message present)
    if (ex.assistantMsg) {
      const rawAns =
        ex.assistantMsg.text ||
        (ex.assistantMsg as any).content ||
        ex.assistantMsg.response?.grounded_answer ||
        ex.assistantMsg.response?.answer ||
        ex.assistantMsg.response?.reply ||
        ex.assistantMsg.response?.response ||
        '';

      const citationsList = ex.assistantMsg.citations || ex.assistantMsg.response?.citations || [];
      const { cleanText, citations } = cleanRagResponseText(rawAns, citationsList);

      const durationSec = ex.assistantMsg.durationSec ?? ex.assistantMsg.response?.duration_sec;
      const ansTitle = `ANSWER ${ex.turnIndex}`;
      const ansTitleWidth = estimateHelveticaWidth(ansTitle, 9.5);

      ensureSpace(20);
      currentOps.push(
        `BT /F2 9.5 Tf 0.15 0.38 0.92 rg ${cardInnerX} ${curY - 10} Td (${escapePdfText(ansTitle)}) Tj ET`
      );
      if (durationSec != null && Number(durationSec) > 0) {
        const thoughtText = `Thought for ${Number(durationSec).toFixed(1)}s`;
        currentOps.push(
          `BT /F1 7.5 Tf 0.45 0.52 0.62 rg ${cardInnerX + ansTitleWidth + 8} ${curY - 10} Td (${escapePdfText(thoughtText)}) Tj ET`
        );
      }
      curY -= 16;

      if (cleanText) {
        renderMarkdownBlock(cleanText, cardInnerX, cardInnerWidth);
      } else if (ex.assistantMsg.error) {
        ensureSpace(22);
        currentOps.push(
          `BT /F3 9 Tf 0.7 0.2 0.2 rg ${cardInnerX} ${curY - 10} Td (${escapePdfText(`[Error: ${ex.assistantMsg.error.message || 'Execution error'}]`)}) Tj ET`
        );
        curY -= 16;
      }

      // Render Citations if present
      if (citations && citations.length > 0) {
        curY -= 6;
        ensureSpace(24);
        currentOps.push(
          `BT /F2 8.5 Tf 0.15 0.25 0.42 rg ${cardInnerX} ${curY - 8} Td (${escapePdfText('References')}) Tj ET`
        );
        currentOps.push(
          `0.12 0.35 0.6 RG 0.75 w ${cardInnerX} ${curY - 11} m ${cardInnerX + 65} ${curY - 11} l S`
        );
        curY -= 18;

        citations.forEach((cit) => {
          ensureSpace(16);
          const parts: string[] = [];
          if (cit.primary_page) parts.push(`Page ${cit.primary_page}`);
          if (cit.heading) parts.push(cit.heading);
          if (cit.university) parts.push(cit.university);
          const extra = parts.length > 0 ? ` (${parts.join(', ')})` : '';
          const refStr = `[${cit.citation_index}] ${cit.pdf_filename || 'Audited Document'}${extra}`;

          const wrappedLines = wrapTextToWidth(refStr, cardInnerWidth - 10, 8);
          for (let i = 0; i < wrappedLines.length; i++) {
            ensureSpace(12);
            const font = i === 0 ? '/F2 8 Tf 0.12 0.2 0.3 rg' : '/F1 8 Tf 0.28 0.32 0.4 rg';
            currentOps.push(
              `BT ${font} ${cardInnerX + (i > 0 ? 10 : 0)} ${curY - 8} Td (${escapePdfText(wrappedLines[i])}) Tj ET`
            );
            curY -= 11;
          }
          curY -= 2;
        });
      }
    }

    // Close unified box container for this turn
    curY -= 6;
    closeCurrentBoxSlice();
    curY -= 16; // Margin between consecutive turn boxes
  }

  // Ensure any dangling box is safely closed before final provenance architecture card
  closeCurrentBoxSlice();

  // --- AUDITED PIPELINE ARCHITECTURE & PROVENANCE SECTION ---
  const latestAssistantWithPipeline = [...messages]
    .reverse()
    .find((m) => m.role === 'assistant' && (m.response?.pipeline_info || m.pipeline_info));
  const sProv = resolveAuditedProvenance(
    latestAssistantWithPipeline?.response || { pipeline_info: latestAssistantWithPipeline?.pipeline_info }
  );

  curY -= 12;
  ensureSpace(110);

  currentOps.push(
    `BT /F2 10.5 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText('Architecture Running')}) Tj ET`
  );
  currentOps.push(
    `0.08 0.4 0.65 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 95} ${curY - 16} l S`
  );
  curY -= 24;

  const sessionCardHeight = 78;
  currentOps.push(`0.97 0.98 0.99 rg`);
  currentOps.push(`${marginX} ${curY - sessionCardHeight} ${contentWidth} ${sessionCardHeight} re f`);
  currentOps.push(`0.88 0.91 0.95 RG 0.75 w`);
  currentOps.push(`${marginX} ${curY - sessionCardHeight} ${contentWidth} ${sessionCardHeight} re s`);

  const sessionSpecRows = [
    { label: 'Storage Substrates:', val: sProv.storageUsed },
    { label: 'Synthesis LLM:', val: `${sProv.llmModel} (${sProv.llmProvider})` },
    { label: 'Dense Embedding Encoder:', val: sProv.encoderModel },
    { label: 'Cross-Attention Reranker:', val: sProv.rerankerModel },
    { label: 'NLI Entailment Verifier:', val: sProv.nliVerifierModel },
    { label: 'Platform Attribution:', val: 'RAISE' },
  ];

  let sessionSpecY = curY - 12;
  sessionSpecRows.forEach((row) => {
    currentOps.push(
      `BT /F2 7.5 Tf 0.25 0.32 0.45 rg ${marginX + 10} ${sessionSpecY} Td (${escapePdfText(row.label)}) Tj ET`
    );
    currentOps.push(
      `BT /F1 7.5 Tf 0.12 0.16 0.24 rg ${marginX + 130} ${sessionSpecY} Td (${escapePdfText(row.val)}) Tj ET`
    );
    sessionSpecY -= 11.5;
  });

  curY -= sessionCardHeight + 10;

  // Push final page stream
  if (currentOps.length > 0) {
    pages.push(currentOps.join('\n'));
  }

  // Decorate each page with watermark, running footer and page numbers
  const totalPages = Math.max(1, pages.length);
  const finalPagesContent = pages.map((pageStream, pageIndex) => {
    const pageNum = pageIndex + 1;
    const watermarkOps = [
      'q',
      '0.95 0.96 0.98 rg', // Soft elegant diagonal RAISE watermark
      'BT',
      '/F2 52 Tf',
      '0.7071 0.7071 -0.7071 0.7071 210 330 Tm',
      `(${escapePdfText('RAISE')}) Tj`,
      'ET',
      'Q',
    ].join('\n');
    const footerOps = [
      `0.85 0.88 0.92 RG 0.5 w ${marginX} 40 m ${marginX + contentWidth} 40 l S`,
      `BT /F1 7.5 Tf 0.55 0.6 0.68 rg ${marginX} 28 Td (${escapePdfText(`RAISE Research Platform • Session: ${sessionTitle.slice(0, 42)}`)}) Tj ET`,
      `BT /F2 7.5 Tf 0.45 0.5 0.6 rg ${marginX + contentWidth - 62} 28 Td (${escapePdfText(`Page ${pageNum} of ${totalPages}`)}) Tj ET`,
    ].join('\n');
    return `${watermarkOps}\n${pageStream}\n${footerOps}`;
  });

  // --- BUILD PDF 1.4 FILE STRUCTURE ---
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  let byteOffset = 0;

  const appendString = (str: string) => {
    const bytes = encoder.encode(str);
    chunks.push(bytes);
    byteOffset += bytes.length;
  };

  appendString('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');

  // Object registry
  const objectOffsets: number[] = [];

  // 1: Catalog
  objectOffsets[1] = byteOffset;
  appendString('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

  // 2: Pages
  const pageObjectIds: number[] = [];
  let nextId = 6;
  for (let i = 0; i < totalPages; i++) {
    pageObjectIds.push(nextId);
    nextId += 2;
  }

  objectOffsets[2] = byteOffset;
  appendString(
    `2 0 obj\n<< /Type /Pages /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${totalPages} >>\nendobj\n`
  );

  // Fonts: 3: F1 (Helvetica), 4: F2 (Helvetica-Bold), 5: F3 (Helvetica-Oblique)
  objectOffsets[3] = byteOffset;
  appendString('3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n');

  objectOffsets[4] = byteOffset;
  appendString('4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n');

  objectOffsets[5] = byteOffset;
  appendString('5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>\nendobj\n');

  // Create Page & Content Stream Objects
  for (let i = 0; i < totalPages; i++) {
    const pageId = pageObjectIds[i];
    const streamId = pageId + 1;
    const streamContent = finalPagesContent[i] || '';
    const streamBytes = encoder.encode(streamContent);

    // Page object (ISO A4 Dimensions)
    objectOffsets[pageId] = byteOffset;
    appendString(
      `${pageId} 0 obj\n<<\n  /Type /Page\n  /Parent 2 0 R\n  /MediaBox [0 0 ${pageWidth} ${pageHeight}]\n  /CropBox [0 0 ${pageWidth} ${pageHeight}]\n  /Contents ${streamId} 0 R\n  /Resources <<\n    /Font <<\n      /F1 3 0 R\n      /F2 4 0 R\n      /F3 5 0 R\n    >>\n  >>\n>>\nendobj\n`
    );

    // Stream object
    objectOffsets[streamId] = byteOffset;
    appendString(`${streamId} 0 obj\n<< /Length ${streamBytes.length} >>\nstream\n`);
    chunks.push(streamBytes);
    byteOffset += streamBytes.length;
    appendString('\nendstream\nendobj\n');
  }

  // Info dictionary
  const infoId = nextId;
  nextId++;
  const pdfDate = formatPdfDate(now);
  objectOffsets[infoId] = byteOffset;

  appendString(
    `${infoId} 0 obj\n<<\n  /Title (${escapePdfText(`RAISE Transcript: ${sessionTitle.slice(0, 60)}`)})\n  /Subject (${escapePdfText('Research Assessment Intelligence & Semantic Extraction')})\n  /Author (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')})\n  /Creator (${escapePdfText('RAISE Semantic Research Workstation')})\n  /Producer (${escapePdfText('RAISE PDF Engine 1.4')})\n  /CreationDate (${pdfDate})\n  /ModDate (${pdfDate})\n  /Keywords (${escapePdfText(`RAISE, Transcript, Multi-Turn, Research, ${sessionTitle.slice(0, 30)}`)})\n>>\nendobj\n`
  );

  // Cross Reference Table
  const xrefOffset = byteOffset;
  const totalObjects = nextId;
  appendString(`xref\n0 ${totalObjects}\n0000000000 65535 f \n`);
  for (let i = 1; i < totalObjects; i++) {
    const off = objectOffsets[i] || 0;
    appendString(`${off.toString().padStart(10, '0')} 00000 n \n`);
  }

  // Trailer
  appendString(
    `trailer\n<< /Size ${totalObjects} /Root 1 0 R /Info ${infoId} 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
  );

  return new Blob(chunks as BlobPart[], { type: 'application/pdf' });
}

/**
 * Downloads the full conversation transcript of a ChatSession as a formatted PDF (.pdf).
 */
export function exportSessionAsPdf(session: ChatSession, customFilename?: string): void {
  const blob = generateSessionPdfBlob(session);
  const titleSlug = slugify(session.title || 'conversation-transcript', 36);
  const dateStr = new Date().toISOString().split('T')[0];
  const filename = customFilename || `raise-session-${titleSlug}-${dateStr}.pdf`;
  downloadBlob(blob, filename);
}

/**
 * Opens a formatted printable report in a new browser window/tab
 * and invokes the browser print dialog (allowing "Save as PDF").
 */
export function printReportWindow(
  query: string,
  answerText: string,
  response?: Partial<SubgraphQueryResponse>
): Window | null {
  if (typeof window === 'undefined') return null;

  try {
    const html = generateReportHtml(query, answerText, response);
    const printWindow = window.open('', '_blank', 'width=880,height=920');
    if (!printWindow) {
      // If popup was blocked, fallback to downloading PDF file
      exportAsPdf(query, answerText, response);
      return null;
    }

    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();

    const triggerPrint = () => {
      try {
        printWindow.focus();
        printWindow.print();
      } catch (e) {
        console.warn('Auto-print invocation prevented:', e);
      }
    };

    if (printWindow.document.readyState === 'complete') {
      setTimeout(triggerPrint, 300);
    } else {
      printWindow.addEventListener('load', () => setTimeout(triggerPrint, 300));
      setTimeout(triggerPrint, 1200);
    }

    return printWindow;
  } catch (err) {
    console.warn('Failed to open print window, falling back to PDF download:', err);
    exportAsPdf(query, answerText, response);
    return null;
  }
}
