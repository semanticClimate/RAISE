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

    // If conversation is short (e.g. 1 message) and content doesn't overflow significantly,
    // ensure scroll-to-bottom button is hidden and lock is released
    const maxScroll = container.scrollHeight - container.clientHeight;
    if (maxScroll <= 100) {
      isAutoScrollLockedRef.current = false;
      setIsAutoScrollLocked(false);
      setShowScrollToBottom(false);
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
        const maxScrollable = scrollHeight - clientHeight;

        // If content fits on screen without overflow, or if conversation is empty,
        // never show scroll to bottom button
        if (maxScrollable <= 100 || conversation.length === 0) {
          if (isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = false;
            setIsAutoScrollLocked(false);
          }
          setShowScrollToBottom(false);
          return;
        }

        const scrollTop = container.scrollTop;
        const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);

        // Only show button if user has scrolled up away from bottom by > 120px
        if (distanceFromBottom > 120) {
          if (!isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = true;
            setIsAutoScrollLocked(true);
          }
          setShowScrollToBottom(true);
        } else if (distanceFromBottom <= 30) {
          // User scrolled back down near bottom
          if (isAutoScrollLockedRef.current) {
            isAutoScrollLockedRef.current = false;
            setIsAutoScrollLocked(false);
          }
          setShowScrollToBottom(false);
        }
      });
    };

    const handleWheel = () => {
      // Check actual scroll geometry on wheel rather than blindly setting true
      checkScrollPosition();
    };

    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        touchStartYRef.current = e.touches[0].clientY;
      }
    };

    const handleTouchMove = () => {
      // Check actual scroll geometry on touch scroll
      checkScrollPosition();
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
