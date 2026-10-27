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

// Disallowed commands explicitly purged per UI cleanup specifications (e.g. decommissioned commands)
export const DISALLOWED_SLASH_COMMANDS = new Set(['/synthesize', '/graph', '/bench']);

/**
 * Standard default slash commands available even when offline or before initial probe.
 * User interface presents /boost, /compare and /browser as core research commands.
 */
export const DEFAULT_SLASH_COMMANDS: SlashCommand[] = [
  {
    name: '/boost',
    syntax: '/boost [mode: fast|expert|clear|status]',
    description: 'Hardware acceleration & tier status',
    category: 'Performance',
    examples: ['/boost', '/boost fast', '/boost expert', '/boost status'],
    aliases: ['/turbo', '/accelerate', '/perf', '/optimize'],
    is_dev_only: false,
  },
  {
    name: '/compare',
    syntax: '/compare [focus: research|academics|finance|faculty|sustainability]',
    description: 'Side-by-side document comparison',
    category: 'Comparison',
    examples: ['/compare', '/compare research', '/compare finance'],
    aliases: ['/diff', '/versus', '/vs'],
    is_dev_only: false,
  },
  {
    name: '/browser',
    syntax: '/browser [url or search topic]',
    description: 'Search and extract web data',
    category: 'Research',
    examples: ['/browser NIRF Rankings IIT Madras', '/browser https://en.wikipedia.org/wiki/Harvard_University'],
    aliases: ['/web', '/fetch', '/internet'],
    is_dev_only: false,
  },
];

/**
 * Diagnostic commands for developer view mode (/audit and /help)
 */
export const DEV_SLASH_COMMANDS: SlashCommand[] = [
  ...DEFAULT_SLASH_COMMANDS,
  {
    name: '/audit',
    syntax: '/audit [claim or section]',
    description: 'Verify claims & citations',
    category: 'Verification',
    examples: ['/audit', '/audit patents and publications'],
    aliases: ['/verify', '/factcheck'],
    is_dev_only: true,
  },
  {
    name: '/help',
    syntax: '/help',
    description: 'Usage commands & shortcuts',
    category: 'Help',
    examples: ['/help'],
    aliases: ['/commands'],
    is_dev_only: true,
  },
];
