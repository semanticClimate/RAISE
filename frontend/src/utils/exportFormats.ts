import type { SubgraphQueryResponse } from '../types';
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

  // Research Inquiry
  lines.push('## Research Inquiry');
  lines.push('');
  lines.push(`> ${query || 'General Academic & Institutional Query'}`);
  lines.push('');
  lines.push('---');
  lines.push('');

  // Clean answer text & format citations
  const { cleanText } = cleanRagResponseText(answerText, response?.citations || []);

  // RAISE Synthesis Section
  lines.push('## RAISE : Research Synthesis');
  lines.push('');
  lines.push(cleanText.trim());
  lines.push('');

  // Citations & References Section
  if (response?.citations && response.citations.length > 0) {
    lines.push('---');
    lines.push('');
    lines.push('## References & Grounded Citations');
    lines.push('');

    response.citations.forEach((cit) => {
      const idx = cit.citation_index;
      const file = cit.pdf_filename || 'Audited Institutional Document';
      const page = cit.primary_page ? `Page ${cit.primary_page}` : 'Page N/A';
      const uni = cit.university ? `, ${cit.university}` : '';
      const text = cit.plain_text ? cit.plain_text.trim() : '';
      const chunk = cit.chunk_id ? `\`${cit.chunk_id}\`` : '`chunk-ref`';
      const sim = typeof cit.similarity === 'number' ? cit.similarity.toFixed(3) : null;

      lines.push(`### [${idx}] ${file} (${page}${uni})`);
      if (text) {
        lines.push(`> "${text}"`);
      }
      lines.push(`- *Chunk ID:* ${chunk}${sim ? ` | *Relevance Similarity:* \`${sim}\`` : ''}`);
      lines.push('');
    });
  }



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
  return {
    export_version: '1.0.0',
    platform: 'RAISE: Research Assessment Intelligence & Semantic Extraction',
    exported_at: new Date().toISOString(),
    query: query || response?.query || '',
    answer: answerText,
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

  const uniqueDocs = Array.from(
    new Set((response?.citations || []).map((c) => c.pdf_filename).filter(Boolean))
  ) as string[];
  const uniqueUnis = Array.from(
    new Set((response?.citations || []).map((c) => c.university).filter(Boolean))
  ) as string[];
  const citationsCount = response?.citations?.length || 0;

  const { cleanText } = cleanRagResponseText(answerText, response?.citations || []);

  // Basic markdown to HTML paragraph & heading transformer with justified alignment
  const formattedAnswerHtml = cleanText
    .split('\n\n')
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return '';
      if (trimmed.startsWith('### ')) {
        return `<h3 style="font-size: 16px; font-weight: 700; color: #0284c7; margin-top: 20px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">${escapeHtml(
          trimmed.slice(4)
        )}</h3>`;
      }
      if (trimmed.startsWith('## ')) {
        return `<h2 style="font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 24px; margin-bottom: 10px;">${escapeHtml(
          trimmed.slice(3)
        )}</h2>`;
      }
      if (trimmed.startsWith('# ')) {
        return `<h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 28px; margin-bottom: 12px;">${escapeHtml(
          trimmed.slice(2)
        )}</h1>`;
      }

      // Format bullet lists with justified text
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        const items = trimmed
          .split('\n')
          .map((li) => li.replace(/^[-*]\s+/, ''))
          .map(
            (li) =>
              `<li style="margin-bottom: 7px; text-align: justify; text-justify: inter-word; line-height: 1.65; hyphens: auto; -webkit-hyphens: auto;">${formatInlineMarkdown(li)}</li>`
          )
          .join('');
        return `<ul style="margin: 12px 0; padding-left: 24px; color: #334155; line-height: 1.65;">${items}</ul>`;
      }

      return `<p style="margin-bottom: 12px; color: #334155; line-height: 1.7; font-size: 14.5px; text-align: justify; text-justify: inter-word; hyphens: auto; -webkit-hyphens: auto;">${formatInlineMarkdown(
        trimmed
      )}</p>`;
    })
    .join('\n');

  // Citations HTML
  let citationsHtml = '';
  if (response?.citations && response.citations.length > 0) {
    const rows = response.citations
      .map(
        (cit) => `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; break-inside: avoid;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="color: #0f172a; font-size: 13px;">[${cit.citation_index}] ${escapeHtml(
              cit.pdf_filename || 'Document'
            )}</strong>
            <span style="font-family: monospace; font-size: 12px; color: #0284c7; background: #e0f2fe; padding: 2px 8px; border-radius: 4px;">Page ${
              cit.primary_page || 'N/A'
            }</span>
          </div>
          ${
            cit.plain_text
              ? `<blockquote style="margin: 6px 0; padding-left: 12px; border-left: 3px solid #cbd5e1; font-style: italic; color: #475569; font-size: 12.5px; text-align: justify; text-justify: inter-word;">"${escapeHtml(
                  cit.plain_text
                )}"</blockquote>`
              : ''
          }
          <div style="font-size: 11px; color: #64748b; margin-top: 6px; display: flex; justify-content: space-between; align-items: center;">
            <span>Chunk: <code>${escapeHtml(cit.chunk_id || 'N/A')}</code></span>
            ${
              typeof cit.similarity === 'number'
                ? `<span>Similarity: <strong>${cit.similarity.toFixed(3)}</strong></span>`
                : ''
            }
          </div>
        </div>
      `
      )
      .join('');

    citationsHtml = `
      <section style="margin-top: 36px; break-before: auto;">
        <h2 style="font-size: 18px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #0284c7; padding-bottom: 6px; margin-bottom: 16px;">
          Grounded References & Sources (${response.citations.length})
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
    }
    p, li, blockquote {
      text-align: justify;
      text-justify: inter-word;
      hyphens: auto;
      -webkit-hyphens: auto;
    }
    .print-banner {
      background: #0f172a;
      color: #ffffff;
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
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 6px;">Research Inquiry</div>
    <div style="font-size: 15px; font-weight: 600; color: #0f172a; line-height: 1.4;">${escapeHtml(
      query || 'General Inquiry'
    )}</div>
  </div>

  <main>
    <h2 style="font-size: 18px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 16px;">
      RAISE : Research Synthesis
    </h2>
    <div style="font-size: 14.5px;">
      ${formattedAnswerHtml}
    </div>

    ${citationsHtml}
  </main>

  <footer style="margin-top: 48px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
    Generated by RAISE — Research Assessment Intelligence & Semantic Extraction • ISO A4 Justified Edition
  </footer>
</body>
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatInlineMarkdown(text: string): string {
  let escaped = escapeHtml(text);
  // Bold **text**
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Code `code`
  escaped = escaped.replace(
    /`(.*?)`/g,
    '<code style="background: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-size: 12px; font-family: monospace;">$1</code>'
  );
  // Citation badges [1] or [1, 2]
  escaped = escaped.replace(
    /\[(\d+(?:\s*,\s*\d+)*)\]/g,
    '<span style="display: inline-block; padding: 1px 5px; font-size: 11px; font-family: monospace; font-weight: 600; color: #0284c7; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 4px; margin: 0 2px;">[$1]</span>'
  );
  return escaped;
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
        default:
          return ' ';
      }
    });
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
function wordWrap(text: string, maxCharsPerLine: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = '';

  for (const w of words) {
    if (!w) continue;
    if (cur.length === 0) {
      cur = w;
    } else if (cur.length + 1 + w.length <= maxCharsPerLine) {
      cur += ' ' + w;
    } else {
      lines.push(cur);
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

  // Metadata Extraction
  const uniqueDocs = Array.from(
    new Set((response?.citations || []).map((c) => c.pdf_filename).filter(Boolean))
  ) as string[];
  const uniqueUnis = Array.from(
    new Set((response?.citations || []).map((c) => c.university).filter(Boolean))
  ) as string[];
  const totalCitations = response?.citations?.length || 0;

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
  currentOps.push(`0.06 0.09 0.16 rg`); // Dark Navy
  currentOps.push(`${marginX} ${curY - 36} ${contentWidth} 36 re f`);
  currentOps.push(
    `BT /F2 11 Tf 1 1 1 rg ${marginX + 12} ${curY - 18} Td (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')}) Tj ET`
  );
  currentOps.push(
    `BT /F1 7.5 Tf 0.7 0.78 0.9 rg ${marginX + 12} ${curY - 29} Td (${escapePdfText('ISO A4 Standard • Justified Research Intelligence Report')}) Tj ET`
  );
  currentOps.push(
    `BT /F1 8 Tf 1 1 1 rg ${marginX + contentWidth - 85} ${curY - 22} Td (${escapePdfText(`${dateStr} ${timeStr}`)}) Tj ET`
  );
  curY -= 42;

  // --- METADATA STRIP ---
  ensureSpace(24);
  const metaBoxHeight = 20;
  currentOps.push(`0.96 0.97 0.99 rg 0.88 0.91 0.95 RG 0.5 w`);
  currentOps.push(`${marginX} ${curY - metaBoxHeight} ${contentWidth} ${metaBoxHeight} re b`);

  const metaLeft = `A4 (210 x 297 mm)  •  Justified  •  Audited Citations: ${totalCitations}`;
  const metaRight =
    uniqueUnis.length > 0
      ? `Institute: ${uniqueUnis.slice(0, 2).join(', ').slice(0, 30)}`
      : uniqueDocs.length > 0
        ? `Corpus: ${uniqueDocs[0].slice(0, 30)}`
        : 'Research Corpus';
  currentOps.push(
    `BT /F2 7.5 Tf 0.25 0.35 0.5 rg ${marginX + 8} ${curY - 13} Td (${escapePdfText(metaLeft)}) Tj ET`
  );
  currentOps.push(
    `BT /F1 7.5 Tf 0.4 0.48 0.58 rg ${marginX + contentWidth - 170} ${curY - 13} Td (${escapePdfText(metaRight)}) Tj ET`
  );
  curY -= metaBoxHeight + 8;

  // --- QUERY BOX ---
  ensureSpace(45);
  const queryLines = wordWrap(query || 'Research Inquiry', 85);
  const queryBoxHeight = Math.max(34, queryLines.length * 13 + 18);
  currentOps.push(`0.96 0.97 0.99 rg 0.85 0.88 0.92 RG 0.5 w`);
  currentOps.push(`${marginX} ${curY - queryBoxHeight} ${contentWidth} ${queryBoxHeight} re b`);
  currentOps.push(
    `BT /F2 8 Tf 0.35 0.45 0.55 rg ${marginX + 10} ${curY - 14} Td (${escapePdfText('RESEARCH INQUIRY')}) Tj ET`
  );
  let qTextY = curY - 26;
  for (const ql of queryLines) {
    currentOps.push(
      `BT /F1 9.5 Tf 0.1 0.15 0.22 rg ${marginX + 10} ${qTextY} Td (${escapePdfText(ql)}) Tj ET`
    );
    qTextY -= 13;
  }
  curY -= queryBoxHeight + 14;

  // --- SECTION HEADER: RAISE SYNTHESIS ---
  ensureSpace(25);
  currentOps.push(
    `BT /F2 11 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText('RAISE : Research Synthesis')}) Tj ET`
  );
  currentOps.push(
    `0.08 0.12 0.22 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 170} ${curY - 16} l S`
  );
  curY -= 28;

  // --- ANSWER BODY RENDERING WITH TYPOGRAPHIC JUSTIFICATION ---
  const { cleanText } = cleanRagResponseText(answerText, response?.citations || []);
  const answerParagraphs = cleanText.split('\n');
  for (const rawLine of answerParagraphs) {
    const trimmed = rawLine.trim();
    if (!trimmed) {
      curY -= 6;
      continue;
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
    const wrapped = wordWrap(cleanBulletText, isBullet ? 84 : 90);
    const targetLineWidth = contentWidth - (isBullet ? 12 : 0);

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

  // --- CITATIONS & REFERENCES SECTION ---
  if (response?.citations && response.citations.length > 0) {
    curY -= 12;
    ensureSpace(32);
    currentOps.push(
      `BT /F2 11 Tf 0.08 0.12 0.22 rg ${marginX} ${curY - 12} Td (${escapePdfText(`GROUNDED REFERENCES & AUDITED SOURCES (${response.citations.length})`)}) Tj ET`
    );
    currentOps.push(
      `0.08 0.4 0.65 RG 1.5 w ${marginX} ${curY - 16} m ${marginX + 230} ${curY - 16} l S`
    );
    curY -= 26;

    response.citations.forEach((cit) => {
      ensureSpace(42);
      const headerStr = `[${cit.citation_index}] ${cit.pdf_filename || 'Audited Document'} - Page ${cit.primary_page || 'N/A'}${cit.university ? ` (${cit.university})` : ''}`;
      currentOps.push(
        `BT /F2 9 Tf 0.08 0.15 0.25 rg ${marginX} ${curY - 10} Td (${escapePdfText(headerStr)}) Tj ET`
      );
      curY -= 13;

      if (cit.plain_text) {
        const quoteLines = wordWrap(`"${cit.plain_text}"`, 88);
        const quoteTargetWidth = contentWidth - 20;

        for (let qIdx = 0; qIdx < Math.min(quoteLines.length, 4); qIdx++) {
          ensureSpace(12);
          const ql = quoteLines[qIdx];
          const isLastQuote = qIdx === Math.min(quoteLines.length, 4) - 1;
          const words = ql.trim().split(/\s+/);
          let qWordSpacing = 0;

          if (!isLastQuote && words.length > 1) {
            const est = estimateHelveticaWidth(ql, 8.5);
            const diff = quoteTargetWidth - est;
            if (diff > 0 && diff < 65) {
              qWordSpacing = diff / (words.length - 1);
            }
          }

          if (qWordSpacing > 0) {
            currentOps.push(
              `BT /F3 8.5 Tf ${qWordSpacing.toFixed(2)} Tw 0.3 0.35 0.42 rg ${marginX + 10} ${curY - 9} Td (${escapePdfText(ql)}) Tj 0 Tw ET`
            );
          } else {
            currentOps.push(
              `BT /F3 8.5 Tf 0.3 0.35 0.42 rg ${marginX + 10} ${curY - 9} Td (${escapePdfText(ql)}) Tj ET`
            );
          }
          curY -= 11.5;
        }
      }

      const metaStr = `Chunk: ${cit.chunk_id || 'N/A'}${typeof cit.similarity === 'number' ? ` | Similarity: ${cit.similarity.toFixed(3)}` : ''}`;
      ensureSpace(12);
      currentOps.push(
        `BT /F1 7.5 Tf 0.5 0.55 0.6 rg ${marginX + 10} ${curY - 8} Td (${escapePdfText(metaStr)}) Tj ET`
      );
      curY -= 14;
    });
  }

  // Push final page stream
  if (currentOps.length > 0) {
    pages.push(currentOps.join('\n'));
  }

  // Decorate each page with footer and page numbers
  const totalPages = Math.max(1, pages.length);
  const finalPagesContent = pages.map((pageStream, pageIndex) => {
    const pageNum = pageIndex + 1;
    const footerOps = [
      `0.85 0.88 0.92 RG 0.5 w ${marginX} 40 m ${marginX + contentWidth} 40 l S`,
      `BT /F1 7.5 Tf 0.55 0.6 0.68 rg ${marginX} 28 Td (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction • ISO A4 Justified')}) Tj ET`,
      `BT /F1 7.5 Tf 0.55 0.6 0.68 rg ${marginX + contentWidth - 55} 28 Td (${escapePdfText(`Page ${pageNum} of ${totalPages}`)}) Tj ET`,
    ].join('\n');
    return `${pageStream}\n${footerOps}`;
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
    `${infoId} 0 obj\n<<\n  /Title (${escapePdfText(`RAISE Report: ${query.slice(0, 60) || 'Research Inquiry'}${safeDocTitle}`)})\n  /Subject (${escapePdfText('Research Assessment Intelligence & Semantic Extraction')})\n  /Author (${escapePdfText('RAISE: Research Assessment Intelligence & Semantic Extraction')})\n  /Creator (${escapePdfText('RAISE Semantic Research Platform')})\n  /Producer (${escapePdfText('RAISE PDF Engine 1.4 (ISO A4 Justified)')})\n  /CreationDate (${pdfDate})\n  /ModDate (${pdfDate})\n  /Keywords (${escapePdfText(keywordsStr)})\n>>\nendobj\n`
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

    // Trigger print once document is loaded
    setTimeout(() => {
      try {
        printWindow.focus();
        printWindow.print();
      } catch (e) {
        console.warn('Auto-print invocation prevented:', e);
      }
    }, 400);

    return printWindow;
  } catch (err) {
    console.warn('Failed to open print window, falling back to PDF download:', err);
    exportAsPdf(query, answerText, response);
    return null;
  }
}
