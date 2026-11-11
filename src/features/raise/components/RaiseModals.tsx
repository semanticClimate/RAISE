import React, { Suspense, lazy } from 'react';
import { isLocalEnvironment } from '../../control-center/services/platformAdapter';
import type { ChatSession, SourceDocument } from '../types';
import { PdfViewerModal } from './PdfViewerModal';

const LibraryPickerModal = lazy(() =>
  import('../../../components/library/LibraryPickerModal').then((m) => ({
    default: m.LibraryPickerModal,
  }))
);
const ControlCenterModal = lazy(() =>
  import('../../control-center/ControlCenterModal').then((m) => ({
    default: m.ControlCenterModal,
  }))
);
const MainSettingsModal = lazy(() =>
  import('../../settings/SettingsModal').then((m) => ({ default: m.SettingsModal }))
);
const MainSearchModal = lazy(() =>
  import('../../sidebar/search/SearchModal').then((m) => ({ default: m.SearchModal }))
);

export interface RaiseModalsProps {
  isSettingsOpen: boolean;
  theme: any;
  setTheme: (t: any) => void;
  onSelectLibraryDocument: (doc: any) => void;
  onDeleteSourceDoc: (id: string, name: string) => void;
  sessions: ChatSession[];
  onSessionsChange: React.Dispatch<React.SetStateAction<ChatSession[]>>;
  onDeleteAllChats: () => void;
  selectedVoiceName: string;
  setSelectedVoiceName: (v: string) => void;
  availableVoices: SpeechSynthesisVoice[];
  isVoiceSamplePlaying: boolean;
  onPlaySample: () => void;
  isControlCenterOpen: boolean;
  isSearchModalOpen: boolean;
  onCloseSearchModal: () => void;
  sortedSessions: ChatSession[];
  currentSessionId: string | null;
  pinnedSessionIds: string[];
  sourceDocs: SourceDocument[];
  activeSessionMenuId: string | null;
  setActiveSessionMenuId: (id: string | null) => void;
  renamingSessionId: string | null;
  setRenamingSessionId: (id: string | null) => void;
  newSessionTitle: string;
  setNewSessionTitle: (t: string) => void;
  handleSaveRename: (id: string) => void;
  handleTogglePinSession: (id: string) => void;
  handleDeleteSession: (id: string) => void;
  onSelectSession: (s: ChatSession) => void;
  onNewChat: () => void;
  isLibraryPickerOpen: boolean;
  onCloseLibraryPicker: () => void;
  onBrowseFileClick: () => void;
  onOpenPdfViewer: (file: string, pageNumber?: number) => void;
  activePdfCitation: any;
  onClosePdfViewer: () => void;
}

export const RaiseModals: React.FC<RaiseModalsProps> = ({
  isSettingsOpen,
  theme,
  setTheme,
  onSelectLibraryDocument,
  onDeleteSourceDoc,
  sessions,
  onSessionsChange,
  onDeleteAllChats,
  selectedVoiceName,
  setSelectedVoiceName,
  availableVoices,
  isVoiceSamplePlaying,
  onPlaySample,
  isControlCenterOpen,
  isSearchModalOpen,
  onCloseSearchModal,
  sortedSessions,
  currentSessionId,
  pinnedSessionIds,
  sourceDocs,
  activeSessionMenuId,
  setActiveSessionMenuId,
  renamingSessionId,
  setRenamingSessionId,
  newSessionTitle,
  setNewSessionTitle,
  handleSaveRename,
  handleTogglePinSession,
  handleDeleteSession,
  onSelectSession,
  onNewChat,
  isLibraryPickerOpen,
  onCloseLibraryPicker,
  onBrowseFileClick,
  onOpenPdfViewer,
  activePdfCitation,
  onClosePdfViewer,
}) => {
  return (
    <>
      {isSettingsOpen && (
        <Suspense fallback={null}>
          <MainSettingsModal
            theme={theme}
            setTheme={setTheme}
            onSelectLibraryDocument={onSelectLibraryDocument}
            onDeleteSourceDoc={onDeleteSourceDoc}
            sessions={sessions}
            onSessionsChange={onSessionsChange}
            onDeleteAllChats={onDeleteAllChats}
            selectedVoiceName={selectedVoiceName}
            setSelectedVoiceName={setSelectedVoiceName}
            availableVoices={availableVoices}
            isPlayingSample={isVoiceSamplePlaying}
            onPlaySample={onPlaySample}
          />
        </Suspense>
      )}

      {isControlCenterOpen && isLocalEnvironment() && (
        <Suspense fallback={null}>
          <ControlCenterModal />
        </Suspense>
      )}

      {isSearchModalOpen && (
        <Suspense fallback={null}>
          <MainSearchModal
            isOpen={isSearchModalOpen}
            onClose={onCloseSearchModal}
            sessions={sortedSessions}
            currentSessionId={currentSessionId}
            pinnedSessionIds={pinnedSessionIds}
            sourceDocs={sourceDocs}
            activeSessionMenuId={activeSessionMenuId}
            setActiveSessionMenuId={setActiveSessionMenuId}
            renamingSessionId={renamingSessionId}
            setRenamingSessionId={setRenamingSessionId}
            newSessionTitle={newSessionTitle}
            setNewSessionTitle={setNewSessionTitle}
            handleSaveRename={handleSaveRename}
            handleTogglePinSession={handleTogglePinSession}
            handleDeleteSession={handleDeleteSession}
            onSelectSession={onSelectSession}
            onNewChat={onNewChat}
          />
        </Suspense>
      )}

      {isLibraryPickerOpen && (
        <Suspense fallback={null}>
          <LibraryPickerModal
            isOpen={isLibraryPickerOpen}
            onClose={onCloseLibraryPicker}
            onSelectDocument={onSelectLibraryDocument}
            attachedDocNames={sourceDocs.filter((d) => d.selected).map((d) => d.name)}
            onOpenUploadFromPC={onBrowseFileClick}
            onViewPdf={onOpenPdfViewer}
            onAttachAll={(items) => {
              items.forEach((item) => {
                onSelectLibraryDocument(item);
              });
            }}
          />
        </Suspense>
      )}

      <PdfViewerModal
        isOpen={Boolean(activePdfCitation)}
        citation={activePdfCitation}
        onClose={onClosePdfViewer}
      />
    </>
  );
};
