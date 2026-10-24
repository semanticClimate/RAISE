import { type ApiResponse, apiClient } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import {
  CommandsResponseSchema,
  DEFAULT_SLASH_COMMANDS,
  DEV_SLASH_COMMANDS,
  type SlashCommand,
} from '../schemas/commands';

export class CommandService {
  private static cachedCommands: SlashCommand[] | null = null;
  private static cachedIncludeDev = false;
  private static lastFetchTime = 0;
  private static readonly CACHE_TTL_MS = 60_000; // 1 minute

  /**
   * Fetch registered slash commands from the backend API.
   * If remote discovery is unavailable or times out, safely falls back
   * to deterministic DEFAULT_SLASH_COMMANDS (or DEV_SLASH_COMMANDS if includeDev).
   */
  public async getCommands(
    signal?: AbortSignal,
    includeDev = false,
    forceRefresh = false
  ): Promise<ApiResponse<SlashCommand[]>> {
    const now = Date.now();
    if (
      !forceRefresh &&
      CommandService.cachedCommands &&
      CommandService.cachedIncludeDev === includeDev &&
      now - CommandService.lastFetchTime < CommandService.CACHE_TTL_MS
    ) {
      return {
        data: CommandService.cachedCommands,
        error: null,
        status: 200,
        isMock: false,
      };
    }

    const fallbackCommands = includeDev ? DEV_SLASH_COMMANDS : DEFAULT_SLASH_COMMANDS;

    try {
      const endpoint = includeDev ? `${ENDPOINTS.COMMANDS}?include_dev=true` : ENDPOINTS.COMMANDS;
      const res = await apiClient.request(
        endpoint,
        CommandsResponseSchema,
        {
          method: 'GET',
          signal,
          timeoutMs: 4000,
        }
      );

      if (res.data?.commands && res.data.commands.length > 0) {
        CommandService.cachedCommands = res.data.commands;
        CommandService.cachedIncludeDev = includeDev;
        CommandService.lastFetchTime = now;
        return {
          data: res.data.commands,
          error: null,
          status: res.status,
          isMock: res.isMock,
        };
      }
    } catch {
      // Graceful fallback to default commands
    }

    // Default fallback
    CommandService.cachedCommands = fallbackCommands;
    CommandService.cachedIncludeDev = includeDev;
    CommandService.lastFetchTime = now;
    return {
      data: fallbackCommands,
      error: null,
      status: 200,
      isMock: false,
    };
  }

  /**
   * Return synchronous cached commands or standard defaults immediately
   */
  public getCachedCommands(includeDev = false): SlashCommand[] {
    if (CommandService.cachedCommands && CommandService.cachedIncludeDev === includeDev) {
      return CommandService.cachedCommands;
    }
    return includeDev ? DEV_SLASH_COMMANDS : DEFAULT_SLASH_COMMANDS;
  }
}

export const commandService = new CommandService();
