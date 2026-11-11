import { useEffect, useState } from 'react';

export const ANIMATED_PLACEHOLDER_PROMPTS = [
  'Ask any question..',
  'Ask any question about research & innovations..',
  'Ask any question about patents & publications..',
  'Ask any question about documents & analysis..',
];

export function useQueryBoxTypewriter(conversationLength: number, query: string, customPlaceholder?: string) {
  const [placeholderText, setPlaceholderText] = useState(customPlaceholder || 'Ask any question..');
  const [promptIndex, setPromptIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (customPlaceholder) {
      setPlaceholderText(customPlaceholder);
      return;
    }

    if (conversationLength > 0 || query.length > 0) return;

    const currentPrompt =
      ANIMATED_PLACEHOLDER_PROMPTS[promptIndex % ANIMATED_PLACEHOLDER_PROMPTS.length];
    let timer: ReturnType<typeof setTimeout>;

    if (!isDeleting) {
      if (placeholderText.length < currentPrompt.length) {
        timer = setTimeout(() => {
          setPlaceholderText(currentPrompt.slice(0, placeholderText.length + 1));
        }, 50);
      } else {
        const pauseDuration = promptIndex % ANIMATED_PLACEHOLDER_PROMPTS.length === 0 ? 4500 : 3200;
        timer = setTimeout(() => {
          setIsDeleting(true);
        }, pauseDuration);
      }
    } else {
      if (placeholderText.length > 0) {
        timer = setTimeout(() => {
          setPlaceholderText(currentPrompt.slice(0, placeholderText.length - 1));
        }, 25);
      } else {
        setIsDeleting(false);
        setPromptIndex((prev) => (prev + 1) % ANIMATED_PLACEHOLDER_PROMPTS.length);
      }
    }

    return () => clearTimeout(timer);
  }, [conversationLength, query.length, placeholderText, isDeleting, promptIndex, customPlaceholder]);

  return placeholderText;
}
