import { useEffect } from 'react';

export function useTextareaAutoHeight(
  textareaRef: React.RefObject<HTMLTextAreaElement | null> | undefined,
  query: string,
  conversationLength: number
) {
  useEffect(() => {
    const handleResize = () => {
      const textarea = textareaRef?.current;
      if (!textarea) return;
      const isDesktop = typeof window !== 'undefined' && window.innerWidth >= 640;
      const isNewChat = conversationLength === 0;

      if (!isDesktop) {
        // Mobile / Small Screens (< 640px): strictly compact single-line pill when empty
        textarea.style.height = 'auto';
        const scrollH = textarea.scrollHeight;
        if (!query.trim()) {
          textarea.style.height = `${Math.max(scrollH, 22)}px`;
        } else {
          textarea.style.height = `${Math.min(Math.max(scrollH, 22), 96)}px`;
        }
        return;
      }

      // Desktop: Adaptive height with min-h and max-h boundaries
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      const minHeight = isNewChat ? 52 : 24;
      const maxHeight = 140;

      if (!query.trim()) {
        textarea.style.height = `${minHeight}px`;
      } else {
        textarea.style.height = `${Math.min(Math.max(scrollHeight, minHeight), maxHeight)}px`;
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [textareaRef, query, conversationLength]);
}
