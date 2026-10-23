import { useEffect, useMemo, useState } from 'react';
import { DEFAULT_SLASH_COMMANDS, type SlashCommand } from '../schemas/commands';
import { commandService } from '../services/CommandService';
import { useUiStore } from '../stores/uiStore';

export interface UseSlashCommandsOptions {
  query: string;
  onQueryChange: (newQuery: string) => void;
  onSelectCommand?: (command: SlashCommand) => void;
  selectedDocCount?: number;
}

export function useSlashCommands({
  query,
  onQueryChange,
  onSelectCommand,
}: UseSlashCommandsOptions) {
  const viewMode = useUiStore((s) => s.viewMode);
  const isDeveloper = viewMode === 'developer';

  const [commands, setCommands] = useState<SlashCommand[]>(() => {
    const cached = commandService.getCachedCommands(isDeveloper);
    return isDeveloper ? cached : cached.filter((c) => !c.is_dev_only);
  });
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isDismissed, setIsDismissed] = useState(false);

  // Fetch registered slash commands on mount or when view mode changes
  useEffect(() => {
    let isCancelled = false;
    const controller = new AbortController();

    commandService
      .getCommands(controller.signal, isDeveloper)
      .then((res) => {
        if (!isCancelled && res.data && res.data.length > 0) {
          const visible = isDeveloper
            ? res.data
            : res.data.filter((c) => !c.is_dev_only);
          setCommands(visible.length > 0 ? visible : DEFAULT_SLASH_COMMANDS);
        }
      })
      .catch(() => {
        // Fallback already handled inside commandService
      });

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [isDeveloper]);

  // Determine if slash command menu should be active:
  // Active when query starts with '/' and user hasn't pressed space yet (still typing command)
  const isSlashActive = useMemo(() => {
    if (isDismissed) return false;
    if (!query.startsWith('/')) return false;

    // If query has space (e.g. "/compare research"), command is already entered
    const hasSpace = query.includes(' ');
    return !hasSpace;
  }, [query, isDismissed]);

  // Reset dismissal when query no longer starts with '/'
  useEffect(() => {
    if (!query.startsWith('/')) {
      setIsDismissed(false);
    }
  }, [query]);

  // Extract the filter term (e.g. "/comp" -> "comp")
  const filterTerm = useMemo(() => {
    if (!query.startsWith('/')) return '';
    return query.slice(1).trim().toLowerCase();
  }, [query]);

  // Filter commands by name, aliases, category, or description
  const filteredCommands = useMemo(() => {
    if (!filterTerm) return commands;
    return commands.filter((cmd) => {
      const nameMatch = cmd.name.toLowerCase().includes(filterTerm);
      const aliasMatch = cmd.aliases?.some((a) => a.toLowerCase().includes(filterTerm));
      const categoryMatch = cmd.category.toLowerCase().includes(filterTerm);
      const descMatch = cmd.description.toLowerCase().includes(filterTerm);
      return nameMatch || aliasMatch || categoryMatch || descMatch;
    });
  }, [commands, filterTerm]);

  // Keep selected index within bounds
  useEffect(() => {
    if (selectedIndex >= filteredCommands.length) {
      setSelectedIndex(0);
    }
  }, [filteredCommands.length, selectedIndex]);

  // Apply command selection
  const selectCommand = (command: SlashCommand) => {
    onQueryChange(`${command.name} `);
    setIsDismissed(true);
    onSelectCommand?.(command);
  };

  const handleKeyDown = (e: React.KeyboardEvent): boolean => {
    if (!isSlashActive || filteredCommands.length === 0) {
      return false;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < filteredCommands.length - 1 ? prev + 1 : 0));
      return true;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filteredCommands.length - 1));
      return true;
    }

    if ((e.key === 'Enter' || e.key === 'Tab') && !e.shiftKey) {
      e.preventDefault();
      const target = filteredCommands[selectedIndex];
      if (target) {
        selectCommand(target);
        return true;
      }
    }

    if (e.key === 'Escape') {
      e.preventDefault();
      setIsDismissed(true);
      return true;
    }

    return false;
  };

  return {
    commands,
    filteredCommands,
    isOpen: isSlashActive && filteredCommands.length > 0,
    selectedIndex,
    setSelectedIndex,
    selectCommand,
    handleKeyDown,
    dismiss: () => setIsDismissed(true),
  };
}
