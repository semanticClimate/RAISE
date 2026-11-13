import type React from 'react';
import type { DynamicSuggestion } from '../../../types';

export interface QuerySuggestionsListProps {
  showSuggestions: boolean;
  filteredSuggestions: DynamicSuggestion[];
  activeSuggestionIndex: number;
  onQueryChange: (query: string) => void;
  setShowSuggestions: (show: boolean) => void;
  setActiveSuggestionIndex: React.Dispatch<React.SetStateAction<number>>;
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export const QuerySuggestionsList: React.FC<QuerySuggestionsListProps> = ({
  showSuggestions,
  filteredSuggestions,
  activeSuggestionIndex,
  onQueryChange,
  setShowSuggestions,
  setActiveSuggestionIndex,
  textareaRef,
}) => {
  if (!showSuggestions || filteredSuggestions.length === 0) return null;

  return (
    <div
      id="query-suggestions-list"
      data-testid="query-suggestions-list"
      role="listbox"
      aria-label="Prompt Suggestions"
      className="sr-only"
    >
      {filteredSuggestions.map((item, sIdx) => {
        const isHighlighted = activeSuggestionIndex === sIdx;
        return (
          <div
            key={item.query}
            id={`query-suggestion-${sIdx}`}
            data-testid={`query-suggestion-item-${sIdx}`}
            role="option"
            aria-selected={isHighlighted}
            tabIndex={-1}
            onClick={() => {
              onQueryChange(item.query);
              setShowSuggestions(false);
              setActiveSuggestionIndex(-1);
              textareaRef?.current?.focus();
            }}
            onMouseEnter={() => setActiveSuggestionIndex(sIdx)}
          >
            <span>{item.query}</span>
          </div>
        );
      })}
    </div>
  );
};
