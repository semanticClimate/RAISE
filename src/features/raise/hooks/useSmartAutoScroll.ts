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

  // Auto-scroll on new conversation tokens / state update
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

    const isContentBelowFold = (): boolean => {
      if (conversation.length === 0) return false;
      const container = contentContainerRef.current;
      const scrollHeight = container
        ? container.scrollHeight
        : document.documentElement.scrollHeight || document.body.scrollHeight;
      const clientHeight = container ? container.clientHeight : window.innerHeight;
      if (scrollHeight <= clientHeight + 60) return false;

      if (messagesEndRef.current) {
        const rect = messagesEndRef.current.getBoundingClientRect();
        if (rect.top <= clientHeight + 40) {
          return false;
        }
      }

      const scrollTop = container
        ? container.scrollTop
        : window.scrollY || document.documentElement.scrollTop;
      const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
      return distanceFromBottom > 90;
    };

    const checkScrollPosition = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (isContentBelowFold()) {
          setIsAutoScrollLocked(true);
          setShowScrollToBottom(true);
        } else {
          setIsAutoScrollLocked(false);
          setShowScrollToBottom(false);
        }
      });
    };

    const handleWheel = (e: WheelEvent) => {
      if (e.deltaY < -4) {
        if (isContentBelowFold()) {
          setIsAutoScrollLocked(true);
          setShowScrollToBottom(true);
        } else {
          setIsAutoScrollLocked(false);
          setShowScrollToBottom(false);
        }
      } else if (e.deltaY > 4) {
        if (!isContentBelowFold()) {
          setIsAutoScrollLocked(false);
          setShowScrollToBottom(false);
        }
      }
    };

    const containerEl = contentContainerRef.current;
    containerEl?.addEventListener('scroll', checkScrollPosition, { passive: true });
    window.addEventListener('scroll', checkScrollPosition, { passive: true });
    window.addEventListener('wheel', handleWheel, { passive: true });
    window.addEventListener('resize', checkScrollPosition, { passive: true });

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      containerEl?.removeEventListener('scroll', checkScrollPosition);
      window.removeEventListener('scroll', checkScrollPosition);
      window.removeEventListener('wheel', handleWheel);
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
