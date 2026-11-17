import { splitTableRow } from '../../../utils/exportFormats';
import type { Block } from './markdownTypes';

export { type Block };

export function parseMarkdownBlocks(text: string): Block[] {
  const lines = text.split('\n');
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Empty lines
    if (!trimmed) {
      i++;
      continue;
    }

    // 2. Fenced Code Block: ```lang
    if (trimmed.startsWith('```')) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      if (i < lines.length && lines[i].trim().startsWith('```')) {
        i++;
      }
      blocks.push({
        type: 'code',
        language,
        code: codeLines.join('\n'),
      });
      continue;
    }

    // 2.5 LaTeX Block Math: $$ formula $$
    if (trimmed.startsWith('$$')) {
      if (trimmed.length > 4 && trimmed.endsWith('$$')) {
        blocks.push({
          type: 'math',
          formula: trimmed.slice(2, -2).trim(),
        });
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
      blocks.push({
        type: 'math',
        formula: mathLines.join('\n').trim(),
      });
      continue;
    }

    // 3. Horizontal Rule: ---, ***, ___
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' });
      i++;
      continue;
    }

    // 4. Headings: #, ##, ###, #### (or malformed bullets with headings like • ### or • **###)
    const cleanHeadingLine = trimmed.replace(/^[•*-]\s*(?:\*\*)?\s*(#{1,4})/, '$1');
    if (cleanHeadingLine.startsWith('#')) {
      const match = cleanHeadingLine.match(/^(#{1,4})\s+(.*)$/);
      if (match) {
        const level = match[1].length as 1 | 2 | 3 | 4;
        let headingText = match[2].trim();

        // Check if heading line had bold title attached to body text: e.g. "**Title**Body" or "**Title** Body"
        const boldSplit = headingText.match(/^\*\*([^*]+)\*\*(?:\s*)(.+)$/);
        if (boldSplit) {
          headingText = boldSplit[1].trim();
          const remainderText = boldSplit[2].trim();
          blocks.push({
            type: 'heading',
            level,
            text: headingText,
          });
          if (remainderText) {
            blocks.push({
              type: 'paragraph',
              text: remainderText,
            });
          }
          i++;
          continue;
        }

        // Check if heading runs directly into sentence words
        const sentenceSplit = headingText.match(
          /^([A-Z][^.\n]{4,85}?)(?:(?<=[a-z0-9])(?=[A-Z][a-z]+\s+(?:report|study|paper|findings|data|analysis|investigates|demonstrates|presents|highlights|reveals|shows|concludes|from|in|is|are|was|were|aims|focuses|describes))|(?:\.\s+))([\s\S]+)$/
        );
        if (sentenceSplit) {
          headingText = sentenceSplit[1].trim();
          const remainderText = sentenceSplit[2].trim();
          blocks.push({
            type: 'heading',
            level,
            text: headingText,
          });
          if (remainderText) {
            blocks.push({
              type: 'paragraph',
              text: remainderText,
            });
          }
          i++;
          continue;
        }

        // Strip wrapping or trailing asterisks like **Title** or Title**
        headingText = headingText.replace(/^\*+|\*+$/g, '').trim();
        blocks.push({
          type: 'heading',
          level,
          text: headingText,
        });
        i++;
        continue;
      }
    }

    // Standalone bold section header: **Section Title** or known section titles
    if (/^\*\*[^*\n]+\*\*$/.test(trimmed)) {
      const inner = trimmed.slice(2, -2).trim();
      if (!inner.endsWith('.') && inner.length < 80) {
        blocks.push({
          type: 'heading',
          level: 3,
          text: inner,
        });
        i++;
        continue;
      }
    }

    if (
      /^(Key Strategic Conclusions|Institutional Strategic Outcomes|Overarching Institutional Conclusions|Strategic Framework and Economic Targets)$/i.test(
        trimmed
      )
    ) {
      blocks.push({
        type: 'heading',
        level: 3,
        text: trimmed,
      });
      i++;
      continue;
    }

    // 5. Blockquote: > text
    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      blocks.push({
        type: 'blockquote',
        text: quoteLines.join(' '),
      });
      continue;
    }

    // 6. Markdown Table: starts with | and followed by separator
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length) {
      const nextLine = lines[i + 1].trim();
      if (/^\|?(\s*:?-+:?\s*\|)+\s*$/.test(nextLine)) {
        const headers = splitTableRow(trimmed);
        const alignSpecs = splitTableRow(nextLine);
        const alignments = alignSpecs.map((spec) => {
          if (spec.startsWith(':') && spec.endsWith(':')) return 'text-center';
          if (spec.endsWith(':')) return 'text-right';
          return 'text-left';
        });

        i += 2;
        const rows: string[][] = [];
        while (
          i < lines.length &&
          lines[i].trim().startsWith('|') &&
          lines[i].trim().endsWith('|')
        ) {
          const cells = splitTableRow(lines[i]);
          rows.push(cells);
          i++;
        }
        blocks.push({
          type: 'table',
          headers,
          alignments,
          rows,
        });
        continue;
      }
    }

    // 7. Ordered List: 1. Item
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: { num: string; text: string; indent: number }[] = [];
      while (i < lines.length) {
        const currentLine = lines[i];
        const match = currentLine.match(/^(\s*)(\d+)\.\s+(.*)$/);
        if (match) {
          const indent = Math.floor(match[1].length / 2);
          items.push({
            num: match[2],
            text: match[3],
            indent,
          });
          i++;
        } else if (
          items.length > 0 &&
          /^\s{2,}\S/.test(currentLine) &&
          !currentLine.trim().startsWith('#')
        ) {
          items[items.length - 1].text += `\n${currentLine.trim()}`;
          i++;
        } else {
          break;
        }
      }
      blocks.push({
        type: 'ordered-list',
        items,
      });
      continue;
    }

    // 8. Unordered List: * or - or •
    if (/^\s*([*\-•])\s+/.test(line)) {
      const items: { text: string; indent: number }[] = [];
      while (i < lines.length) {
        const currentLine = lines[i];
        const match = currentLine.match(/^(\s*)([*\-•])\s+(.*)$/);
        if (match) {
          const indent = Math.floor(match[1].length / 2);
          items.push({
            text: match[3],
            indent,
          });
          i++;
        } else if (
          items.length > 0 &&
          /^\s{2,}\S/.test(currentLine) &&
          !currentLine.trim().startsWith('#')
        ) {
          items[items.length - 1].text += `\n${currentLine.trim()}`;
          i++;
        } else {
          break;
        }
      }
      blocks.push({
        type: 'unordered-list',
        items,
      });
      continue;
    }

    // 9. Callouts
    if (/^\*\*(Warning|Caution|Alert|Important):\*\*/i.test(trimmed)) {
      blocks.push({
        type: 'callout',
        variant: 'warning',
        text: trimmed,
      });
      i++;
      continue;
    }

    if (/^\*\*(Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(trimmed)) {
      blocks.push({
        type: 'callout',
        variant: 'info',
        text: trimmed,
      });
      i++;
      continue;
    }

    // 10. Standard Paragraph: group contiguous non-blank lines
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
        (nextTrimmed.startsWith('|') && nextTrimmed.endsWith('|')) ||
        /^\*\*(Warning|Caution|Alert|Important|Note|Key Takeaway|Finding|Summary|Takeaway):\*\*/i.test(
          nextTrimmed
        )
      ) {
        break;
      }
      paraLines.push(nextTrimmed);
      i++;
    }

    blocks.push({
      type: 'paragraph',
      text: paraLines.join('\n'),
    });
  }

  return blocks;
}
