import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../types';

export interface UseSmartAutoScrollOptions {
  conversation?: ChatMessage[];
  isLoading?: boolean;
}

export function useSmartAutoScroll(options?: UseSmartAutoScrollOptions) {
  const conversation = options?.conversation ?? [];
  const isLoading = options?.isLoading ?? false;

  const contentContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isAutoScrollLocked, setIsAutoScrollLocked] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  const isAutoScrollLockedRef = useRef(false);
  isAutoScrollLockedRef.current = isAutoScrollLocked;

  const isInitialMountRef = useRef(true);
  const prevConversationLengthRef = useRef(conversation.length);
  const prevIsLoadingRef = useRef(isLoading);

  // Auto-scroll on new user questions or active streaming response tokens
  useEffect(() => {
    // 1. If conversation is empty (hero state), ensure container stays at top and never slides down
    if (conversation.length === 0) {
      if (contentContainerRef.current && contentContainerRef.current.scrollTop !== 0) {
        contentContainerRef.current.scrollTop = 0;
      }
      prevConversationLengthRef.current = 0;
      prevIsLoadingRef.current = false;
      return;
    }

    // 2. Prevent auto-scroll on initial page load / session restore so user can read from where they started
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      prevConversationLengthRef.current = conversation.length;
      prevIsLoadingRef.current = isLoading;
      return;
    }

    const container = contentContainerRef.current;
    if (!container) return;

    const isNewTurn = conversation.length > prevConversationLengthRef.current;
    const isStreaming = isLoading && !isAutoScrollLockedRef.current;

    prevConversationLengthRef.current = conversation.length;
    prevIsLoadingRef.current = isLoading;

    // 3. If a new turn was submitted by the user, unlock and smooth scroll to bottom
    if (isNewTurn && !isLoading) {
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      });
      return;
    }

    // 4. During active streaming tokens, keep scroll pinned to bottom only if user hasn't scrolled up
    if (isStreaming) {
      container.scrollTop = container.scrollHeight;
    }
  }, [conversation, isLoading]);

  const scrollToBottom = useCallback(() => {
    isAutoScrollLockedRef.current = false;
    setIsAutoScrollLocked(false);
    setShowScrollToBottom(false);
    const container = contentContainerRef.current;
    if (container) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, []);

  // Smart scroll & wheel detection: instantly lock on any user upward scroll (wheel, touch, scrollbar)
  useEffect(() => {
    const container = contentContainerRef.current;
    if (!container) return;

    let rafId: number | null = null;

    const checkScrollPosition = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (!container) return;

        const scrollHeight = container.scrollHeight;
        const clientHeight = container.clientHeight;
        const scrollTop = container.scrollTop;
        const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);

        // If distance from bottom is > 35px, user scrolled up: lock auto-scroll and show down-arrow button
        if (distanceFromBottom > 35) {
          if (!isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = true;
            setIsAutoScrollLocked(true);
            setShowScrollToBottom(true);
          }
        } else if (distanceFromBottom <= 10) {
          // User scrolled all the way back to the bottom: restore auto-scroll
          if (isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = false;
            setIsAutoScrollLocked(false);
            setShowScrollToBottom(false);
          }
        }
      });
    };

    const handleWheel = (e: WheelEvent) => {
      // User wheeled up: immediately lock auto-scroll without waiting for scroll animation
      if (e.deltaY < 0) {
        isAutoScrollLockedRef.current = true;
        setIsAutoScrollLocked(true);
        setShowScrollToBottom(true);
      }
    };

    const handleTouchStart = () => {
      // Touch interaction started
    };

    container.addEventListener('scroll', checkScrollPosition, { passive: true });
    container.addEventListener('wheel', handleWheel, { passive: true });
    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    window.addEventListener('resize', checkScrollPosition, { passive: true });

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      container.removeEventListener('scroll', checkScrollPosition);
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('resize', checkScrollPosition);
    };
  }, []);

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
