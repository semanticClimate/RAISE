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

// Sid says: Disallowed commands explicitly purged per UI cleanup specifications
export const DISALLOWED_SLASH_COMMANDS = new Set(['/boost', '/synthesize', '/graph', '/bench']);

/**
 * Standard default slash commands available even when offline or before initial probe.
 * User interface presents /compare and /browser as core research commands.
 */
export const DEFAULT_SLASH_COMMANDS: SlashCommand[] = [
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

/**
 * Set of primary command names and aliases reserved exclusively for developer diagnostic mode.
 */
export const DEV_COMMAND_NAMES = new Set([
  '/audit',
  '/help',
  '/verify',
  '/factcheck',
  '/commands',
]);

/**
 * Determines whether a slash command is classified as developer-only.
 * Guards against backend misconfigurations where /audit and /help omit is_dev_only=True.
 */
export function isDevSlashCommand(command: SlashCommand | { name: string; is_dev_only?: boolean }): boolean {
  if (command.is_dev_only) return true;
  const name = command.name.toLowerCase().trim();
  return DEV_COMMAND_NAMES.has(name);
}

