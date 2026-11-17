import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../types';

export interface UseSmartAutoScrollOptions {
  conversation?: ChatMessage[];
  isLoading?: boolean;
  currentSessionId?: string | null;
}

export function useSmartAutoScroll(options?: UseSmartAutoScrollOptions) {
  const conversation = options?.conversation ?? [];
  const isLoading = options?.isLoading ?? false;
  const currentSessionId = options?.currentSessionId ?? null;

  const contentContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isAutoScrollLocked, setIsAutoScrollLocked] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  const isAutoScrollLockedRef = useRef(false);
  isAutoScrollLockedRef.current = isAutoScrollLocked;

  const isInitialMountRef = useRef(true);
  const prevConversationLengthRef = useRef(conversation.length);
  const prevSessionIdRef = useRef<string | null>(currentSessionId);
  const prevIsLoadingRef = useRef(isLoading);
  const touchStartYRef = useRef<number | null>(null);

  // Auto-scroll on new user questions or active streaming response tokens
  useEffect(() => {
    const container = contentContainerRef.current;

    // 1. If conversation is empty (hero state), ensure container stays at top and never slides down
    if (conversation.length === 0) {
      if (container && container.scrollTop !== 0) {
        container.scrollTop = 0;
      }
      prevConversationLengthRef.current = 0;
      prevSessionIdRef.current = currentSessionId;
      prevIsLoadingRef.current = false;
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      return;
    }

    // 2. Prevent auto-scroll on initial page load / session restore so user can read from where they started
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      prevConversationLengthRef.current = conversation.length;
      prevSessionIdRef.current = currentSessionId;
      prevIsLoadingRef.current = isLoading;
      if (container && container.scrollTop !== 0) {
        container.scrollTop = 0;
      }
      return;
    }

    // 3. If session changed (switching between chats / opening an old chat):
    // Reset to top cleanly without ANY smooth-scroll animation or sliding down.
    if (currentSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = currentSessionId;
      prevConversationLengthRef.current = conversation.length;
      prevIsLoadingRef.current = isLoading;
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      if (container) {
        container.scrollTop = 0;
      }
      return;
    }

    if (!container) return;

    // 4. During active query execution / streaming tokens:
    // Keep scroll pinned to bottom only if the user hasn't scrolled up
    const isStreaming = isLoading && !isAutoScrollLockedRef.current;
    if (isStreaming) {
      container.scrollTop = container.scrollHeight;
    }

    prevConversationLengthRef.current = conversation.length;
    prevIsLoadingRef.current = isLoading;
  }, [conversation, isLoading, currentSessionId]);

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

    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        touchStartYRef.current = e.touches[0].clientY;
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (touchStartYRef.current !== null && e.touches.length > 0) {
        const currentY = e.touches[0].clientY;
        // User dragged finger downwards (scrolling content upwards to see earlier turns)
        if (currentY - touchStartYRef.current > 6) {
          isAutoScrollLockedRef.current = true;
          setIsAutoScrollLocked(true);
          setShowScrollToBottom(true);
        }
      }
    };

    const handleTouchEnd = () => {
      touchStartYRef.current = null;
    };

    container.addEventListener('scroll', checkScrollPosition, { passive: true });
    container.addEventListener('wheel', handleWheel, { passive: true });
    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: true });
    container.addEventListener('touchend', handleTouchEnd, { passive: true });
    window.addEventListener('resize', checkScrollPosition, { passive: true });

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      container.removeEventListener('scroll', checkScrollPosition);
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);
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
