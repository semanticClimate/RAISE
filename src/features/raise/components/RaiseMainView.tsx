import type React from 'react';
import { RAISE_LAYOUT } from '../../../styles/layoutTokens';
import type { useRaiseController } from '../hooks/useRaiseController';
import { QueryBox } from '../query-box';
import { ConversationStream } from './ConversationStream';
import { RaiseHeroHeader } from './RaiseHeroHeader';
import { ScrollToBottomButton } from './ScrollToBottomButton';

export interface RaiseMainViewProps {
  c: ReturnType<typeof useRaiseController>;
}

/**
 * Primary Chat Stream & Query Viewport.
 * Coordinates ConversationStream, Hero Header, Scroll Controls, and QueryBox.
 */
export const RaiseMainView: React.FC<RaiseMainViewProps> = ({ c }) => {
  const isConversationEmpty = c.chatSessions.conversation.length === 0;

  return (
    <div
      ref={c.autoScroll.contentContainerRef}
      className="flex-1 flex flex-col pl-0 sm:pl-16 w-full min-w-0 relative z-10 overflow-y-auto overflow-x-hidden mt-14 sm:mt-16"
    >
      <title>RAISE — Research Assessment Intelligence &amp; Semantic Extraction</title>
      <main
        className={`${RAISE_LAYOUT.streamContainer} ${
          isConversationEmpty
            ? 'flex-1 flex flex-col justify-center min-h-full py-4 sm:py-6 sm:-translate-y-6'
            : 'pt-2 pb-3 sm:pb-4 flex-1 flex flex-col min-h-full'
        } transition-all duration-300`}
      >
        {isConversationEmpty && (
          <RaiseHeroHeader hasSourcesAttached={c.selectedDocs.length > 0} />
        )}

        {!isConversationEmpty && (
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

        <ScrollToBottomButton
          show={c.autoScroll.showScrollToBottom && !isConversationEmpty}
          onScrollToBottom={c.autoScroll.scrollToBottom}
        />

        <div
          className={`${RAISE_LAYOUT.queryColumn} px-0 transition-all duration-300 ${
            isConversationEmpty
              ? 'w-full'
              : 'sticky bottom-3 sm:bottom-5 z-30 mt-2 sm:mt-3'
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
  );
};
