import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useDocumentViewerStore } from '../../../stores/useDocumentViewerStore';
import { detectEnvCredentials } from '../../control-center/services/envDetector';
import { useControlCenterStore } from '../../control-center/store/useControlCenterStore';
import { settingsJunction, useSettingsJunction } from '../../settings/junction';
import { copyMarkdownToClipboard } from '../../../utils/exportFormats';
import type { ChatSession, SourceDocument } from '../types';
import { getInitialSessionId } from '../utils/sessionStorageUtils';
import { useChatEditing } from './useChatEditing';
import { useChatSessions } from './useChatSessions';
import { useChatStream } from './useChatStream';
import { useSessionSources } from './useSessionSources';
import { useSmartAutoScroll } from './useSmartAutoScroll';
import { useSpeechSynthesis } from './useSpeechSynthesis';
import { useVoiceRecognition } from './useVoiceRecognition';

export function useRaiseController() {
  const {
    apiBaseUrl,
    appMode,
    isTunnelConfigured,
    runCapabilityProbe,
    isNeuralReady,
    readinessMessage,
  } = useModeStore();
  const isOnline = appMode === 'connected' || appMode === 'degraded';

  const [theme, setTheme] = useState<'dark' | 'light' | 'system'>(() => {
    try {
      const saved = localStorage.getItem('raise_theme');
      return (saved as 'dark' | 'light' | 'system') || 'dark';
    } catch {
      return 'dark';
    }
  });

  // Auto-probe backend gateway on initial load to resolve 'offline' state
  useEffect(() => {
    runCapabilityProbe();
  }, [runCapabilityProbe]);

  useEffect(() => {
    try {
      localStorage.setItem('raise_theme', theme);
      const root = document.documentElement;
      if (theme === 'dark') {
        root.classList.add('dark');
        root.setAttribute('data-theme', 'dark');
      } else if (theme === 'light') {
        root.classList.remove('dark');
        root.setAttribute('data-theme', 'light');
      } else {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        root.classList.toggle('dark', prefersDark);
        root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
      }
    } catch {}
  }, [theme]);

  const settingsJunctionState = useSettingsJunction();
  const isSettingsOpen = settingsJunctionState.isOpen;

  const isControlCenterOpen = useControlCenterStore((s) => s.isOpen);
  const ccConfig = useControlCenterStore((s) => s.config);
  const openControlCenter = useControlCenterStore((s) => s.setOpen);
  const setControlCenterTab = useControlCenterStore((s) => s.setActiveTab);

  const isLlmConfigured = useMemo(() => {
    if (appMode === 'connected' || appMode === 'degraded') return true;
    if (ccConfig.llmDeployment === 'local') return Boolean(ccConfig.selectedLocalModel);
    const hasConfiguredKey = ccConfig.apiKeys?.some(
      (k) => k.key && k.key.trim().length > 0 && k.provider !== 'unknown'
    );
    if (hasConfiguredKey) return true;
    const envCreds = detectEnvCredentials();
    return envCreds.llmKeys.length > 0;
  }, [appMode, ccConfig]);

  const [query, setQuery] = useState('');
  const [parseMode, setParseModeState] = useState<'fast' | 'expert'>(() => {
    try {
      const saved = localStorage.getItem('raise_research_mode');
      if (saved === 'fast' || saved === 'expert') return saved;
    } catch {}
    return 'fast';
  });

  const setParseMode = useCallback((mode: 'fast' | 'expert') => {
    setParseModeState(mode);
    try {
      localStorage.setItem('raise_research_mode', mode);
    } catch {}
  }, []);
  const [isPipelineDrawerOpen, setIsPipelineDrawerOpen] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [activeSessionMenuId, setActiveSessionMenuId] = useState<string | null>(null);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [newSessionTitle, setNewSessionTitle] = useState('');
  const [pinnedSessionIds, setPinnedSessionIds] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('raise_pinned_sessions');
      return raw ? (JSON.parse(raw) as string[]) : [];
    } catch {
      return [];
    }
  });

  const [editingMessageIndex, setEditingMessageIndex] = useState<number | null>(null);
  const [editingQuestionText, setEditingQuestionText] = useState('');
  const [regeneratingIndex, setRegeneratingIndex] = useState<number | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [expandedQVersionsIndex, setExpandedQVersionsIndex] = useState<number | null>(null);
  const [expandedRespVersionsIndex, setExpandedRespVersionsIndex] = useState<number | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [activePdfCitation, setActivePdfCitation] = useState<any>(null);
  const [selectedVoiceName, setSelectedVoiceName] = useState('Default (Browser)');
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [sourceFilter, setSourceFilter] = useState('');
  const [addSourceMenuOpen, setAddSourceMenuOpen] = useState<'drawer' | 'input' | null>(null);
  const [errorPopup, setErrorPopup] = useState<{
    title: string;
    message?: string;
    onRetry?: () => void;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const activeSessionIdRef = useRef<string | null>(getInitialSessionId());
  const setSessionsProxyRef = useRef<React.Dispatch<React.SetStateAction<ChatSession[]>>>(() => {});
  const abortActiveStreamRef = useRef<() => void>(() => {});

  const speech = useSpeechSynthesis(selectedVoiceName);
  const voice = useVoiceRecognition({ query, setQuery });

  const sessionSources = useSessionSources({
    currentSessionId: activeSessionIdRef.current,
    activeSessionIdRef,
    setSessions: (action) => setSessionsProxyRef.current(action),
  });

  const isAutoScrollLockedRef = useRef<(locked: boolean) => void>(() => {});
  const showScrollToBottomRef = useRef<(show: boolean) => void>(() => {});

  const chatSessions = useChatSessions({
    abortActiveStream: () => abortActiveStreamRef.current(),
    stopSpeaking: speech.stopSpeaking,
    setQuery,
    sourceDocs: sessionSources.sourceDocs,
    setSourceDocs: sessionSources.setSourceDocs,
    apiReadyDocs: sessionSources.apiReadyDocs,
    setIsPipelineDrawerOpen,
    setIsAutoScrollLocked: (val) => isAutoScrollLockedRef.current(val),
    setShowScrollToBottom: (val) => showScrollToBottomRef.current(val),
    setEditingMessageIndex,
    setRegeneratingIndex,
    setCopiedKey,
    setExpandedQVersionsIndex,
    setExpandedRespVersionsIndex,
  });

  activeSessionIdRef.current = chatSessions.currentSessionId;
  setSessionsProxyRef.current = chatSessions.setSessions;

  const chatStream = useChatStream({
    currentSessionId: chatSessions.currentSessionId,
    setCurrentSessionId: chatSessions.setCurrentSessionId,
    conversation: chatSessions.conversation,
    setConversation: chatSessions.setConversation,
    sourceDocs: sessionSources.sourceDocs,
    setIsSourcesDrawerOpen: sessionSources.setIsSourcesDrawerOpen,
    parseMode,
    isLlmConfigured,
    setIsControlCenterOpen: openControlCenter,
    updateSessionInMemory: chatSessions.updateSessionInMemory,
    setIsAutoScrollLocked: (val) => isAutoScrollLockedRef.current(val),
    setShowScrollToBottom: (val) => showScrollToBottomRef.current(val),
  });
  abortActiveStreamRef.current = chatStream.abortActiveQuery;

  const autoScroll = useSmartAutoScroll({
    conversation: chatSessions.conversation,
    isLoading: chatStream?.isLoading ?? false,
    currentSessionId: chatSessions.currentSessionId,
  });

  isAutoScrollLockedRef.current = autoScroll.setIsAutoScrollLocked;
  showScrollToBottomRef.current = autoScroll.setShowScrollToBottom;

  const chatEditing = useChatEditing({
    conversation: chatSessions.conversation,
    setConversation: chatSessions.setConversation,
    currentSessionId: chatSessions.currentSessionId,
    setCurrentSessionId: chatSessions.setCurrentSessionId,
    isLoading: chatStream.isLoading,
    setIsLoading: chatStream.setIsLoading,
    setEditingMessageIndex,
    setRegeneratingIndex,
    setActiveExecutingQuery: chatStream.setActiveExecutingQuery,
    updateSessionInMemory: chatSessions.updateSessionInMemory,
    executeQuery: chatStream.executeQuery,
    setIsAutoScrollLocked: autoScroll.setIsAutoScrollLocked,
    setShowScrollToBottom: autoScroll.setShowScrollToBottom,
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    const loadVoices = () => {
      const v = window.speechSynthesis.getVoices();
      if (v.length > 0) setAvailableVoices(v);
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, []);

  const copyResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyResetTimerRef.current) clearTimeout(copyResetTimerRef.current);
    };
  }, []);

  const handleCopyText = useCallback(async (text: string, key: string) => {
    if (!text) return;
    const copied = await copyMarkdownToClipboard(text);
    if (!copied) return;
    setCopiedKey(key);
    if (copyResetTimerRef.current) clearTimeout(copyResetTimerRef.current);
    copyResetTimerRef.current = setTimeout(() => setCopiedKey(null), 1800);
  }, []);

  const handleTogglePinSession = useCallback((sessionId: string) => {
    setPinnedSessionIds((prev) => {
      const updated = prev.includes(sessionId)
        ? prev.filter((id) => id !== sessionId)
        : [...prev, sessionId];
      try {
        localStorage.setItem('raise_pinned_sessions', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  }, []);

  const handleOpenConfigureLlm = useCallback(() => {
    if (appMode === 'offline') {
      setControlCenterTab('platform');
    } else {
      setControlCenterTab('models');
    }
    openControlCenter(true);
  }, [appMode, openControlCenter, setControlCenterTab]);

  const handleOpenPdfViewer = useCallback((fileName: string, pageNumber: number = 1) => {
    setActivePdfCitation({ pdf_filename: fileName, primary_page: pageNumber });
    useDocumentViewerStore.getState().openDocument(fileName, pageNumber);
  }, []);

  const handleClosePdfViewer = useCallback(() => {
    setActivePdfCitation(null);
    useDocumentViewerStore.getState().closeDocument();
  }, []);

  const selectedDocs = useMemo(
    () => sessionSources.sourceDocs.filter((d) => d.selected),
    [sessionSources.sourceDocs]
  );
  const activeSourcesCount = selectedDocs.length;
  const isDocReady = useCallback((doc: SourceDocument) => doc.status !== 'processing', []);

  const sortedSessions = useMemo(() => {
    return [...chatSessions.sessions].sort((a, b) => {
      const aPinned = pinnedSessionIds.includes(a.id);
      const bPinned = pinnedSessionIds.includes(b.id);
      if (aPinned && !bPinned) return -1;
      if (!aPinned && bPinned) return 1;
      const bTime = new Date(b.updated_at || b.created_at || b.timestamp || 0).getTime();
      const aTime = new Date(a.updated_at || a.created_at || a.timestamp || 0).getTime();
      return bTime - aTime;
    });
  }, [chatSessions.sessions, pinnedSessionIds]);

  const handleSaveRename = useCallback(
    (sessionId: string) => {
      chatSessions.handleSaveRename(sessionId, newSessionTitle);
      setRenamingSessionId(null);
    },
    [chatSessions, newSessionTitle]
  );

  return {
    apiBaseUrl,
    appMode,
    isOnline,
    theme,
    setTheme,
    settingsJunction,
    isSettingsOpen,
    isTunnelConfigured,
    runCapabilityProbe,
    isNeuralReady,
    readinessMessage,
    isControlCenterOpen,
    query,
    setQuery,
    parseMode,
    setParseMode,
    isPipelineDrawerOpen,
    setIsPipelineDrawerOpen,
    isSearchModalOpen,
    setIsSearchModalOpen,
    isUserMenuOpen,
    setIsUserMenuOpen,
    activeSessionMenuId,
    setActiveSessionMenuId,
    renamingSessionId,
    setRenamingSessionId,
    newSessionTitle,
    setNewSessionTitle,
    pinnedSessionIds,
    editingMessageIndex,
    setEditingMessageIndex,
    editingQuestionText,
    setEditingQuestionText,
    regeneratingIndex,
    copiedKey,
    expandedQVersionsIndex,
    expandedRespVersionsIndex,
    setExpandedQVersionsIndex,
    setExpandedRespVersionsIndex,
    showSuggestions,
    setShowSuggestions,
    activeSuggestionIndex,
    setActiveSuggestionIndex,
    activePdfCitation,
    setActivePdfCitation,
    selectedVoiceName,
    setSelectedVoiceName,
    availableVoices,
    sourceFilter,
    setSourceFilter,
    addSourceMenuOpen,
    setAddSourceMenuOpen,
    errorPopup,
    setErrorPopup,
    fileInputRef,
    textareaRef,
    speech,
    voice,
    sessionSources,
    autoScroll,
    chatSessions,
    chatStream,
    chatEditing,
    handleCopyText,
    handleTogglePinSession,
    handleOpenConfigureLlm,
    handleOpenPdfViewer,
    handleClosePdfViewer,
    handleSaveRename,
    selectedDocs,
    activeSourcesCount,
    isDocReady,
    sortedSessions,
  };
}
