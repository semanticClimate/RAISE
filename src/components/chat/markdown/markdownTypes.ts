export type Block =
  | { type: 'heading'; level: 1 | 2 | 3 | 4; text: string }
  | { type: 'code'; language: string; code: string }
  | { type: 'math'; formula: string }
  | { type: 'table'; headers: string[]; alignments: string[]; rows: string[][] }
  | { type: 'blockquote'; text: string }
  | { type: 'ordered-list'; items: { num: string; text: string; indent: number }[] }
  | { type: 'unordered-list'; items: { text: string; indent: number }[] }
  | { type: 'hr' }
  | { type: 'callout'; variant: 'info' | 'warning'; text: string }
  | { type: 'paragraph'; text: string };
