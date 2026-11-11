import React from 'react';
import { getStoredUsername } from '../../app/config';
import { SpecialTooltip } from '../../components/ui/SpecialTooltip';
import { Header as MainHeader, UnconfiguredNotice } from '../header';
import { Sidebar as MainSidebar } from '../sidebar/Sidebar';
import { ActionTooltip } from './components/ActionTooltip';
import { ConversationStream } from './components/ConversationStream';
import { RaiseHeroHeader } from './components/RaiseHeroHeader';
import { RaiseModals } from './components/RaiseModals';
import { SourcesDrawer } from './components/SourcesDrawer';
import { StatusBanners } from './components/StatusBanners';
import { useRaiseController } from './hooks/useRaiseController';
import { QueryBox } from './query-box';
import type {
  ChatMessage,
  ChatSession,
  DynamicSuggestion,
  QuestionVersion,
  ResponseVersion,
  SourceDocument,
} from './types';
import {
  cleanTextForSpeech,
  computeVoiceWaveScale,
  filterNaturalVoices,
  getTurnQuestionVersions,
  ROBOTIC_VOICE_NAMES,
  selectBestSpeechVoice,
} from './utils/speechUtils';

// Re-exports for backwards compatibility with tests and consumers
export type {
  ChatMessage,
  ChatSession,
  DynamicSuggestion,
  QuestionVersion,
  ResponseVersion,
  SourceDocument,
};
export {
  ActionTooltip,
  cleanTextForSpeech,
  computeVoiceWaveScale,
  filterNaturalVoices,
  getTurnQuestionVersions,
  ROBOTIC_VOICE_NAMES,
  SpecialTooltip,
  selectBestSpeechVoice,
};

export const RaisePage: React.FC = () => {
  const c = useRaiseController();

  return (
    <div className="bg-dot-pattern text-slate-900 dark:text-slate-100 h-screen h-dvh max-h-screen max-h-dvh antialiased flex flex-col font-sans select-none overflow-hidden relative">
      <MainHeader
        activeSourcesCount={c.activeSourcesCount}
        onOpenSources={() => c.sessionSources.setIsSourcesDrawerOpen(true)}
        onOpenMobileMenu={() => c.setIsPipelineDrawerOpen(true)}
        isDrawerOpen={c.isPipelineDrawerOpen}
      />

      <UnconfiguredNotice
        isTunnelConfigured={c.isTunnelConfigured}
        onOpenSettings={() => c.settingsJunction.open('gateway')}
      />

      <StatusBanners
        appMode={c.appMode}
        onOpenConfigureLlm={c.handleOpenConfigureLlm}
        onRetryConnection={() => c.runCapabilityProbe()}
        errorPopup={
          c.errorPopup ||
          (c.chatStream.littleErrorPopup
            ? { title: 'Execution Notice', message: c.chatStream.littleErrorPopup }
            : null)
        }
        onCloseErrorPopup={() => {
          c.setErrorPopup(null);
          c.chatStream.setLittleErrorPopup(null);
        }}
      />

      <MainSidebar
        isDrawerOpen={c.isPipelineDrawerOpen}
        onToggleDrawer={() => c.setIsPipelineDrawerOpen((prev) => !prev)}
        onNewChat={c.chatSessions.handleNewChat}
        onOpenSearch={() => {
          c.setIsPipelineDrawerOpen(false);
          c.setIsSearchModalOpen(true);
        }}
        onOpenSettings={() => {
          c.setIsUserMenuOpen(false);
          c.setIsPipelineDrawerOpen(false);
          c.settingsJunction.open();
        }}
        onOpenUsage={() => {
          c.setIsUserMenuOpen(false);
          c.setIsPipelineDrawerOpen(false);
          c.setIsSearchModalOpen(true);
        }}
        onLogout={() => {
          localStorage.clear();
          window.location.reload();
        }}
        sessions={c.sortedSessions}
        currentSessionId={c.chatSessions.currentSessionId}
        pinnedSessionIds={c.pinnedSessionIds}
        activeSessionMenuId={c.activeSessionMenuId}
        renamingSessionId={c.renamingSessionId}
        newSessionTitle={c.newSessionTitle}
        setNewSessionTitle={c.setNewSessionTitle}
        onSelectSession={c.chatSessions.handleSelectSession}
        onTogglePinSession={c.handleTogglePinSession}
        setActiveSessionMenuId={c.setActiveSessionMenuId}
        setRenamingSessionId={c.setRenamingSessionId}
        handleSaveRename={c.handleSaveRename}
        handleDeleteSession={c.chatSessions.handleDeleteSession}
        gatewayUsername={getStoredUsername()}
        isOnline={c.isOnline}
        isTunnelConfigured={c.isTunnelConfigured}
        isUserMenuOpen={c.isUserMenuOpen}
        setIsUserMenuOpen={c.setIsUserMenuOpen}
      />

      {c.isPipelineDrawerOpen && (
        <div
          id="drawerBackdrop"
          onClick={() => c.setIsPipelineDrawerOpen(false)}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity"
        />
      )}

      <SourcesDrawer
        isOpen={c.sessionSources.isSourcesDrawerOpen}
        onClose={() => c.sessionSources.setIsSourcesDrawerOpen(false)}
        sourceDocs={c.sessionSources.sourceDocs}
        activeSourcesCount={c.activeSourcesCount}
        sourceFilter={c.sourceFilter}
        setSourceFilter={c.setSourceFilter}
        addSourceMenuOpen={c.addSourceMenuOpen}
        setAddSourceMenuOpen={c.setAddSourceMenuOpen}
        onBrowseFileClick={() => c.fileInputRef.current?.click()}
        onOpenLibraryPicker={() => c.sessionSources.setIsLibraryPickerOpen(true)}
        isDocReady={c.isDocReady}
        onToggleSourceDoc={c.sessionSources.handleToggleDocSelection}
        onToggleAllSources={(select) =>
          select
            ? c.sessionSources.handleSelectAllDocs()
            : c.sessionSources.handleDeselectAllDocs()
        }
        onDeleteSourceDoc={c.sessionSources.handleRemoveSource}
        onViewPdf={c.handleOpenPdfViewer}
      />

      <div
        ref={c.autoScroll.contentContainerRef}
        className="flex-1 flex flex-col pl-0 sm:pl-16 w-full min-w-0 relative z-10 overflow-y-auto overflow-x-hidden mt-14 sm:mt-16"
      >
        <title>RAISE — Research AI Synthesizer Engine</title>
        <main
          className={`w-full max-w-[clamp(38rem,94vw,62rem)] mx-auto px-[clamp(0.75rem,3vw,1.5rem)] ${
            c.chatSessions.conversation.length === 0
              ? 'flex-1 flex flex-col justify-center min-h-full py-4 sm:py-6 sm:-translate-y-6'
              : 'pt-2 pb-3 sm:pb-4 flex-1 flex flex-col min-h-full'
          } transition-all duration-300`}
        >
          {c.chatSessions.conversation.length === 0 && (
            <RaiseHeroHeader hasSourcesAttached={c.selectedDocs.length > 0} />
          )}

          {c.chatSessions.conversation.length > 0 && (
            <ConversationStream
              conversation={c.chatSessions.conversation}
              activeDocCount={c.activeSourcesCount}
              editingMessageIndex={c.editingMessageIndex}
              editingQuestionText={c.editingQuestionText}
              setEditingMessageIndex={c.setEditingMessageIndex}
              setEditingQuestionText={c.setEditingQuestionText}
              handleSaveEditedQuestion={c.chatEditing.handleSaveEditedQuestion}
              isLoading={c.chatStream.isLoading}
              regeneratingIndex={c.regeneratingIndex}
              speakingMessageId={c.speech.speakingMessageId}
              apiBaseUrl={c.apiBaseUrl}
              appMode={c.appMode}
              currentSessionId={c.chatSessions.currentSessionId}
              sessions={c.chatSessions.sessions}
              forkNotification={c.chatSessions.forkNotification}
              originalNotification={c.chatSessions.originalNotification}
              copiedKey={c.copiedKey}
              expandedQVersionsIndex={c.expandedQVersionsIndex}
              expandedRespVersionsIndex={c.expandedRespVersionsIndex}
              setExpandedQVersionsIndex={c.setExpandedQVersionsIndex}
              setExpandedRespVersionsIndex={c.setExpandedRespVersionsIndex}
              setOriginalNotification={c.chatSessions.setOriginalNotification}
              runCapabilityProbe={c.runCapabilityProbe}
              handleRegenerateResponse={c.chatEditing.handleRegenerateResponse}
              handleCopyText={c.handleCopyText}
              handleToggleSpeak={c.speech.handleToggleSpeak}
              handleForkConversation={c.chatSessions.handleForkConversation}
              handleFeedback={c.chatEditing.handleFeedback}
              handleSwitchQuestionVersion={c.chatEditing.handleSwitchQuestionVersion}
              handleSwitchResponseVersion={c.chatEditing.handleSwitchResponseVersion}
              onSelectSession={c.chatSessions.handleSelectSession}
              onOpenPdfViewer={c.handleOpenPdfViewer}
              onOpenSettings={() => c.settingsJunction.open()}
            />
          )}

          <div ref={c.autoScroll.messagesEndRef} />

          <div
            className={`w-full max-w-[clamp(38rem,94vw,62rem)] mx-auto px-0 transition-all duration-300 ${
              c.chatSessions.conversation.length === 0 ? 'w-full' : 'sticky bottom-0 z-20 pb-2'
            }`}
          >
            <QueryBox
              query={c.query}
              onQueryChange={c.setQuery}
              onSubmit={() => {
                if (!c.query.trim() || c.chatStream.isLoading) return;
                const submitted = c.query;
                c.setQuery('');
                c.chatStream.executeQuery(submitted);
              }}
              onAbort={c.chatStream.abortActiveQuery}
              isLoading={c.chatStream.isLoading}
              conversationLength={c.chatSessions.conversation.length}
              textareaRef={c.textareaRef}
              showSuggestions={c.showSuggestions}
              setShowSuggestions={c.setShowSuggestions}
              filteredSuggestions={[]}
              activeSuggestionIndex={c.activeSuggestionIndex}
              setActiveSuggestionIndex={c.setActiveSuggestionIndex}
              selectedDocs={c.selectedDocs}
              isDocReady={c.isDocReady}
              onRemoveAttachedDoc={c.sessionSources.handleRemoveSource}
              onOpenSourcesDrawer={() => c.sessionSources.setIsSourcesDrawerOpen(true)}
              onViewPdf={c.handleOpenPdfViewer}
              addSourceMenuOpen={c.addSourceMenuOpen}
              setAddSourceMenuOpen={c.setAddSourceMenuOpen}
              fileInputRef={c.fileInputRef}
              onFileUpload={c.sessionSources.handleFileUpload}
              onOpenLibraryPicker={() => c.sessionSources.setIsLibraryPickerOpen(true)}
              parseMode={c.parseMode}
              setParseMode={c.setParseMode}
              isOnline={c.isOnline}
              isListening={c.voice.isListening}
              isVoiceSpeaking={c.voice.isVoiceSpeaking}
              voiceAudioLevels={c.voice.voiceAudioLevels}
              voiceDurationSec={c.voice.voiceDurationSec}
              formatVoiceDuration={c.voice.formatVoiceDuration}
              onToggleVoice={c.voice.handleToggleVoiceQuery}
              onStopVoiceListening={c.voice.stopVoiceListening}
              voiceError={c.voice.voiceError}
              onDismissVoiceError={() => c.voice.setVoiceError(null)}
            />
          </div>
        </main>
      </div>

      <RaiseModals
        isSettingsOpen={c.isSettingsOpen}
        theme={c.theme}
        setTheme={c.setTheme}
        onSelectLibraryDocument={c.sessionSources.handleSelectLibraryDocument}
        onDeleteSourceDoc={c.sessionSources.handleRemoveSource}
        sessions={c.chatSessions.sessions}
        onSessionsChange={c.chatSessions.setSessions}
        onDeleteAllChats={c.chatSessions.handleDeleteAllChats}
        selectedVoiceName={c.selectedVoiceName}
        setSelectedVoiceName={c.setSelectedVoiceName}
        availableVoices={c.availableVoices}
        isVoiceSamplePlaying={c.speech.isVoiceSamplePlaying}
        onPlaySample={c.speech.handleTestVoiceSample}
        isControlCenterOpen={c.isControlCenterOpen}
        isSearchModalOpen={c.isSearchModalOpen}
        onCloseSearchModal={() => {
          c.setIsSearchModalOpen(false);
          c.setActiveSessionMenuId(null);
        }}
        sortedSessions={c.sortedSessions}
        currentSessionId={c.chatSessions.currentSessionId}
        pinnedSessionIds={c.pinnedSessionIds}
        sourceDocs={c.sessionSources.sourceDocs}
        activeSessionMenuId={c.activeSessionMenuId}
        setActiveSessionMenuId={c.setActiveSessionMenuId}
        renamingSessionId={c.renamingSessionId}
        setRenamingSessionId={c.setRenamingSessionId}
        newSessionTitle={c.newSessionTitle}
        setNewSessionTitle={c.setNewSessionTitle}
        handleSaveRename={c.handleSaveRename}
        handleTogglePinSession={c.handleTogglePinSession}
        handleDeleteSession={c.chatSessions.handleDeleteSession}
        onSelectSession={c.chatSessions.handleSelectSession}
        onNewChat={c.chatSessions.handleNewChat}
        isLibraryPickerOpen={c.sessionSources.isLibraryPickerOpen}
        onCloseLibraryPicker={() => c.sessionSources.setIsLibraryPickerOpen(false)}
        onBrowseFileClick={() => c.fileInputRef.current?.click()}
        onOpenPdfViewer={c.handleOpenPdfViewer}
        activePdfCitation={c.activePdfCitation}
        onClosePdfViewer={() => c.setActivePdfCitation(null)}
      />
    </div>
  );
};

export default RaisePage;
