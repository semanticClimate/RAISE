import { z } from 'zod';

export const SlashCommandSchema = z.object({
  name: z.string(),
  syntax: z.string(),
  description: z.string(),
  category: z.string().default('General'),
  examples: z.array(z.string()).default([]),
  aliases: z.array(z.string()).default([]),
  is_dev_only: z.boolean().optional().default(false),
});

export type SlashCommand = z.infer<typeof SlashCommandSchema>;

export const CommandsResponseSchema = z.object({
  status: z.string().default('success'),
  commands: z.array(SlashCommandSchema).default([]),
});

export type CommandsResponse = z.infer<typeof CommandsResponseSchema>;

/**
 * Standard default slash commands available even when offline or before initial probe.
 * User interface presents /compare and /browser as core research commands.
 */
export const DEFAULT_SLASH_COMMANDS: SlashCommand[] = [
  {
    name: '/compare',
    syntax: '/compare [focus: research|academics|finance|faculty|sustainability]',
    description: 'Side-by-side institutional comparison across 17 operational dimensions (requires 2 docs).',
    category: 'Comparison',
    examples: ['/compare', '/compare research', '/compare finance'],
    aliases: ['/diff', '/versus', '/vs'],
    is_dev_only: false,
  },
  {
    name: '/browser',
    syntax: '/browser [url or search topic]',
    description: 'Extract supplemental research facts and public data from the internet.',
    category: 'Research',
    examples: ['/browser NIRF Rankings IIT Madras', '/browser https://en.wikipedia.org/wiki/Harvard_University'],
    aliases: ['/web', '/fetch', '/internet'],
    is_dev_only: false,
  },
];

/**
 * Developer diagnostic commands for developer view mode
 */
export const DEV_SLASH_COMMANDS: SlashCommand[] = [
  ...DEFAULT_SLASH_COMMANDS,
  {
    name: '/audit',
    syntax: '/audit [claim or section]',
    description: 'Strict anti-hallucination factual audit with numerical cross-checking.',
    category: 'Verification',
    examples: ['/audit', '/audit patents and publications'],
    aliases: ['/verify', '/factcheck'],
    is_dev_only: true,
  },
  {
    name: '/synthesize',
    syntax: '/synthesize [focus]',
    description: 'Executive institutional synthesis covering accomplishments, publications, and governance.',
    category: 'Synthesis',
    examples: ['/synthesize', '/synthesize scientific achievements'],
    aliases: ['/summary', '/summarize'],
    is_dev_only: true,
  },
  {
    name: '/graph',
    syntax: '/graph [entity or topic]',
    description: 'Traverse knowledge graph entity networks, projects, and relationships.',
    category: 'Knowledge Graph',
    examples: ['/graph', '/graph Early Flowering 3a'],
    aliases: ['/explore', '/network'],
    is_dev_only: true,
  },
  {
    name: '/bench',
    syntax: '/bench',
    description: 'Run live evaluation across the 8-part industry benchmark suite.',
    category: 'Diagnostics',
    examples: ['/bench'],
    aliases: ['/eval', '/benchmark'],
    is_dev_only: true,
  },
  {
    name: '/help',
    syntax: '/help',
    description: 'Show all available slash commands and usage syntax.',
    category: 'Help',
    examples: ['/help'],
    aliases: ['/commands'],
    is_dev_only: true,
  },
];
