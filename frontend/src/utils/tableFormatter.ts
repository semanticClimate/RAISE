/**
 * Escapes unescaped pipe characters (|) inside a markdown table cell to ensure
 * external GFM parsers do not split the cell into extra columns.
 * Preserves code spans (`...|...`) and already-escaped pipes (\|).
 */
function escapeCellPipes(text: string): string {
  let result = '';
  let inCode = false;
  let i = 0;
  while (i < text.length) {
    const char = text[i];
    if (char === '`') {
      inCode = !inCode;
      result += char;
      i++;
      continue;
    }
    if (char === '|' && !inCode) {
      let backslashCount = 0;
      for (let j = i - 1; j >= 0 && text[j] === '\\'; j--) {
        backslashCount++;
      }
      if (backslashCount % 2 === 0) {
        result += '\\|';
        i++;
        continue;
      }
    }
    result += char;
    i++;
  }
  return result;
}

/**
 * Sanitizes an individual table cell by stripping disruptive newline/tab characters
 * and escaping raw pipes.
 */
function sanitizeCell(cell: unknown): string {
  if (cell === null || cell === undefined) return '';
  const str = String(cell).replace(/\r?\n|\t/g, ' ').trim();
  return escapeCellPipes(str);
}

/**
 * Normalizes column alignment specifiers from Tailwind classes ('text-left', 'text-center', 'text-right'),
 * standard alignment strings ('left', 'center', 'right'), or GFM alignment tokens (':---', ':---:', '---:').
 */
function normalizeAlignment(spec?: string): 'left' | 'center' | 'right' {
  if (!spec) return 'left';
  const s = spec.trim().toLowerCase();
  if (s === 'text-center' || s === 'center' || (s.startsWith(':') && s.endsWith(':'))) {
    return 'center';
  }
  if (s === 'text-right' || s === 'right' || s.endsWith(':')) {
    return 'right';
  }
  return 'left';
}

/**
 * Pads and aligns text within a column according to alignment mode.
 */
function formatCell(text: string, width: number, align: 'left' | 'center' | 'right'): string {
  if (align === 'right') {
    return text.padStart(width, ' ');
  }
  if (align === 'center') {
    const totalPad = width - text.length;
    const padLeft = Math.floor(totalPad / 2);
    const padRight = totalPad - padLeft;
    return `${' '.repeat(padLeft)}${text}${' '.repeat(padRight)}`;
  }
  return text.padEnd(width, ' ');
}

/**
 * Formats table headers, column alignments, and data rows into clean,
 * standard GitHub-Flavored Markdown (GFM) table text.
 * Suitable for copying to clipboard for pasting into markdown editors,
 * Google Docs, Google Sheets, Excel, or spreadsheets.
 */
export function formatTableAsMarkdown(
  headers: string[],
  alignments: string[],
  rows: string[][]
): string {
  if ((!headers || headers.length === 0) && (!rows || rows.length === 0)) {
    return '';
  }

  const colCount = Math.max(
    headers?.length || 0,
    ...(rows || []).map((r) => r?.length || 0),
    0
  );
  if (colCount === 0) return '';

  const sanitizedHeaders = Array.from({ length: colCount }, (_, c) =>
    sanitizeCell(headers?.[c])
  );
  const sanitizedRows = (rows || []).map((row) =>
    Array.from({ length: colCount }, (_, c) => sanitizeCell(row?.[c]))
  );

  // Determine width of each column (minimum 3 chars for standard GFM separator e.g. ---)
  const colWidths: number[] = [];
  for (let c = 0; c < colCount; c++) {
    let maxLen = sanitizedHeaders[c].length;
    for (const row of sanitizedRows) {
      if (row[c].length > maxLen) {
        maxLen = row[c].length;
      }
    }
    colWidths[c] = Math.max(maxLen, 3);
  }

  // Header line: | Header 1 | Header 2 |
  const headerCells = sanitizedHeaders.map((text, c) => {
    const align = normalizeAlignment(alignments?.[c]);
    return formatCell(text, colWidths[c], align);
  });
  const headerLine = `| ${headerCells.join(' | ')} |`;

  // Separator line: | :--- | :---: | ---: |
  const sepCells = Array.from({ length: colCount }, (_, c) => {
    const align = normalizeAlignment(alignments?.[c]);
    const width = colWidths[c];
    if (align === 'center') {
      const dashes = Math.max(1, width - 2);
      return `:${'-'.repeat(dashes)}:`;
    }
    if (align === 'right') {
      const dashes = Math.max(2, width - 1);
      return `${'-'.repeat(dashes)}:`;
    }
    return '-'.repeat(width);
  });
  const sepLine = `| ${sepCells.join(' | ')} |`;

  // Data rows: | Cell 1 | Cell 2 |
  const rowLines = sanitizedRows.map((row) => {
    const cells = row.map((text, c) => {
      const align = normalizeAlignment(alignments?.[c]);
      return formatCell(text, colWidths[c], align);
    });
    return `| ${cells.join(' | ')} |`;
  });

  return [headerLine, sepLine, ...rowLines].join('\n');
}
