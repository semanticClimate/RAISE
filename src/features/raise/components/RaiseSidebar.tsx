import type React from 'react';
import { getStoredUsername } from '../../../app/config';
import { Sidebar as MainSidebar } from '../../sidebar/Sidebar';
import type { useRaiseController } from '../hooks/useRaiseController';

export interface RaiseSidebarProps {
  c: ReturnType<typeof useRaiseController>;
}

export const RaiseSidebar: React.FC<RaiseSidebarProps> = ({ c }) => {
  return (
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
  );
};
