import type React from 'react';
import { Header as MainHeader, UnconfiguredNotice } from '../header';
import { RaiseMainView } from './components/RaiseMainView';
import { RaiseModalsContainer } from './components/RaiseModalsContainer';
import { RaiseSidebar } from './components/RaiseSidebar';
import { SourcesDrawer } from './components/SourcesDrawer';
import { StatusBanners } from './components/StatusBanners';
import { useRaiseController } from './hooks/useRaiseController';

/**
 * Route Entry: RaisePage
 * Composition and layout wiring only; zero inline logic or keyframes.
 * Adheres strictly to Route / Page Entry line budget (40-80 target, 100 max).
 */
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
            ? {
                title: 'Execution Notice',
                message: c.chatStream.littleErrorPopup,
              }
            : null)
        }
        onCloseErrorPopup={() => {
          c.setErrorPopup(null);
          c.chatStream.setLittleErrorPopup(null);
        }}
      />

      <RaiseSidebar c={c} />

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

      <RaiseMainView c={c} />

      <RaiseModalsContainer c={c} />
    </div>
  );
};

export default RaisePage;
