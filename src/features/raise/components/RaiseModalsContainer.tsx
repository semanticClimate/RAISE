import type React from 'react';
import type { useRaiseController } from '../hooks/useRaiseController';
import { RaiseModals } from './RaiseModals';

export interface RaiseModalsContainerProps {
  c: ReturnType<typeof useRaiseController>;
}

export const RaiseModalsContainer: React.FC<RaiseModalsContainerProps> = ({
  c,
}) => {
  return (
    <RaiseModals
      isSettingsOpen={c.isSettingsOpen}
      theme={c.theme}
      setTheme={c.setTheme}
      onSelectLibraryDocument={c.sessionSources.handleSelectLibraryDocument}
      onDeleteSourceDoc={c.sessionSources.handleRemoveSource}
      onToggleSelectDoc={c.sessionSources.handleToggleDocSelection}
      onDeselectAllDocs={c.sessionSources.handleDeselectAllDocs}
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
      onCloseLibraryPicker={() =>
        c.sessionSources.setIsLibraryPickerOpen(false)
      }
      onBrowseFileClick={() => c.fileInputRef.current?.click()}
      onOpenPdfViewer={c.handleOpenPdfViewer}
      activePdfCitation={c.activePdfCitation}
      onClosePdfViewer={c.handleClosePdfViewer}
    />
  );
};
