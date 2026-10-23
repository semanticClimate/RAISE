import { z } from 'zod';

export const SlashCommandSchema = z.object({
  name: z.string(),
  syntax: z.string(),
  description: z.string(),
  category: z.string().default('General'),
  examples: z.array(z.string()).default([]),
  aliases: z.array(z.string()).default([]),
});

export type SlashCommand = z.infer<typeof SlashCommandSchema>;

export const CommandsResponseSchema = z.object({
  status: z.string().default('success'),
  commands: z.array(SlashCommandSchema).default([]),
});

export type CommandsResponse = z.infer<typeof CommandsResponseSchema>;

/**
 * Standard default slash commands available even when offline or before initial probe
 */
export const DEFAULT_SLASH_COMMANDS: SlashCommand[] = [
  {
    name: '/compare',
    syntax: '/compare [focus: research|academics|finance|faculty|sustainability]',
    description: 'Side-by-side institutional comparison across 17 operational dimensions (requires 2 docs).',
    category: 'Comparison',
    examples: ['/compare', '/compare research', '/compare finance'],
    aliases: ['/diff', '/versus', '/vs'],
  },
  {
    name: '/audit',
    syntax: '/audit [claim or section]',
    description: 'Strict anti-hallucination factual audit with numerical cross-checking.',
    category: 'Verification',
    examples: ['/audit', '/audit patents and publications'],
    aliases: ['/verify', '/factcheck'],
  },
  {
    name: '/synthesize',
    syntax: '/synthesize [focus]',
    description: 'Executive institutional synthesis covering accomplishments, publications, and governance.',
    category: 'Synthesis',
    examples: ['/synthesize', '/synthesize scientific achievements'],
    aliases: ['/summary', '/summarize'],
  },
  {
    name: '/graph',
    syntax: '/graph [entity or topic]',
    description: 'Traverse knowledge graph entity networks, projects, and relationships.',
    category: 'Knowledge Graph',
    examples: ['/graph', '/graph Early Flowering 3a'],
    aliases: ['/explore', '/network'],
  },
  {
    name: '/bench',
    syntax: '/bench',
    description: 'Run live evaluation across the 8-part industry benchmark suite.',
    category: 'Diagnostics',
    examples: ['/bench'],
    aliases: ['/eval', '/benchmark'],
  },
  {
    name: '/help',
    syntax: '/help',
    description: 'Show all available slash commands and usage syntax.',
    category: 'Help',
    examples: ['/help'],
    aliases: ['/commands'],
  },
];
