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
  const prevSessionIdRef = useRef<string | null>(currentSessionId);
  const touchStartYRef = useRef<number | null>(null);

  // Auto-scroll on new conversation tokens / state update ONLY IF not locked by user
  useEffect(() => {
    const container = contentContainerRef.current;
    if (!container) return;

    // 1. If conversation is empty (hero state), ensure container stays at top
    if (conversation.length === 0) {
      if (container.scrollTop !== 0) {
        container.scrollTop = 0;
      }
      prevSessionIdRef.current = currentSessionId;
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      return;
    }

    // 2. Initial mount or session switch (opening an old chat):
    // Instantly jump to the bottom without any slow, disorienting smooth-scroll sliding animation
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      prevSessionIdRef.current = currentSessionId;
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'auto',
      });
      return;
    }

    if (currentSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = currentSessionId;
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'auto',
      });
      return;
    }

    // 3. Normal streaming / new message update: only auto-scroll if user has not scrolled up
    if (!isAutoScrollLocked && conversation.length > 0) {
      const scrollBehavior: ScrollBehavior = isLoading ? 'auto' : 'smooth';
      if (typeof container.scrollTo === 'function') {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: scrollBehavior,
        });
      } else if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
        messagesEndRef.current.scrollIntoView({ behavior: scrollBehavior, block: 'end' });
      }
    }
  }, [conversation, isLoading, isAutoScrollLocked, currentSessionId]);

  const scrollToBottom = useCallback(() => {
    isAutoScrollLockedRef.current = false;
    setIsAutoScrollLocked(false);
    setShowScrollToBottom(false);
    if (typeof contentContainerRef.current?.scrollTo === 'function') {
      contentContainerRef.current.scrollTo({
        top: contentContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    } else if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, []);

  // Smart scroll & wheel detection: ALWAYS register on containerEl on mount regardless of conversation.length
  useEffect(() => {
    const containerEl = contentContainerRef.current;
    if (!containerEl) return;

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

        // If distance from bottom is > 80px, user scrolled up -> LOCK auto-scroll & show button
        if (distanceFromBottom > 80) {
          if (!isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = true;
            setIsAutoScrollLocked(true);
            setShowScrollToBottom(true);
          }
        } else if (distanceFromBottom <= 20) {
          // User scrolled all the way back to the bottom -> restore auto-scroll & hide button
          if (isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = false;
            setIsAutoScrollLocked(false);
            setShowScrollToBottom(false);
          }
        }
      });
    };

    const handleWheel = (e: WheelEvent) => {
      // User wheeled up: immediately lock auto-scroll and show button
      if (e.deltaY < -2) {
        isAutoScrollLockedRef.current = true;
        setIsAutoScrollLocked(true);
        setShowScrollToBottom(true);
      } else if (e.deltaY > 2) {
        checkScrollPosition();
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

    containerEl.addEventListener('scroll', checkScrollPosition, { passive: true });
    containerEl.addEventListener('wheel', handleWheel, { passive: true });
    containerEl.addEventListener('touchstart', handleTouchStart, { passive: true });
    containerEl.addEventListener('touchmove', handleTouchMove, { passive: true });
    containerEl.addEventListener('touchend', handleTouchEnd, { passive: true });
    window.addEventListener('resize', checkScrollPosition, { passive: true });

    return () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      containerEl.removeEventListener('scroll', checkScrollPosition);
      containerEl.removeEventListener('wheel', handleWheel);
      containerEl.removeEventListener('touchstart', handleTouchStart);
      containerEl.removeEventListener('touchmove', handleTouchMove);
      containerEl.removeEventListener('touchend', handleTouchEnd);
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
