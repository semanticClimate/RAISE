import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../types';

export interface UseSmartAutoScrollOptions {
  conversation: ChatMessage[];
  isLoading: boolean;
}

export function useSmartAutoScroll({ conversation, isLoading }: UseSmartAutoScrollOptions) {
  const contentContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isAutoScrollLocked, setIsAutoScrollLocked] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const isAutoScrollLockedRef = useRef(false);
  isAutoScrollLockedRef.current = isAutoScrollLocked;

  // Auto-scroll on new conversation tokens / state update ONLY IF not locked by user
  useEffect(() => {
    if (!isAutoScrollLocked) {
      const scrollBehavior: ScrollBehavior = isLoading ? 'auto' : 'smooth';
      if (typeof contentContainerRef.current?.scrollTo === 'function') {
        contentContainerRef.current.scrollTo({
          top: contentContainerRef.current.scrollHeight,
          behavior: scrollBehavior,
        });
      } else if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
        messagesEndRef.current.scrollIntoView({ behavior: scrollBehavior, block: 'end' });
      }
    }
  }, [conversation, isLoading, isAutoScrollLocked]);

  const scrollToBottom = useCallback(() => {
    setIsAutoScrollLocked(false);
    setShowScrollToBottom(false);
    if (typeof contentContainerRef.current?.scrollTo === 'function') {
      contentContainerRef.current.scrollTo({
        top: contentContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, []);

  // Smart scroll & wheel detection with requestAnimationFrame throttling to eliminate layout thrashing
  useEffect(() => {
    if (conversation.length === 0) {
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      return;
    }

    let rafId: number | null = null;

    const checkScrollPosition = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        const container = contentContainerRef.current;
        if (!container) return;

        const scrollHeight = container.scrollHeight;
        const clientHeight = container.clientHeight;
        const scrollTop = container.scrollTop;
        const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);

        // If distance from bottom is > 80px, user scrolled up
        if (distanceFromBottom > 80) {
          setIsAutoScrollLocked(true);
          setShowScrollToBottom(true);
        } else {
          setIsAutoScrollLocked(false);
          setShowScrollToBottom(false);
        }
      });
    };

    const handleWheel = (e: WheelEvent) => {
      // User wheeled up: immediately lock auto-scroll and show button
      if (e.deltaY < -2) {
        setIsAutoScrollLocked(true);
        setShowScrollToBottom(true);
      } else if (e.deltaY > 2) {
        checkScrollPosition();
      }
    };

    const containerEl = contentContainerRef.current;
    containerEl?.addEventListener('scroll', checkScrollPosition, { passive: true });
    containerEl?.addEventListener('wheel', handleWheel, { passive: true });
    window.addEventListener('resize', checkScrollPosition, { passive: true });

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      containerEl?.removeEventListener('scroll', checkScrollPosition);
      containerEl?.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', checkScrollPosition);
    };
  }, [conversation.length]);

  return {
    contentContainerRef,
    messagesEndRef,
    isAutoScrollLocked,
    setIsAutoScrollLocked,
    showScrollToBottom,
    setShowScrollToBottom,
    scrollToBottom,
  };
}
