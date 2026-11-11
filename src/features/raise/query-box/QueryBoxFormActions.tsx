import type React from 'react';
import { VoiceInputButton } from '../../../components/input/VoiceInputButton';
import type { SourceDocument } from '../../../types';
import { AddSourceButton, AttachedDocChips, FastExpertToggle } from '../query-controls';

export interface QueryBoxFormActionsProps {
  query: string;
  isLoading: boolean;
  conversationLength: number;
  addSourceMenuOpen: 'input' | 'drawer' | null;
  setAddSourceMenuOpen: React.Dispatch<React.SetStateAction<'input' | 'drawer' | null>>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onOpenLibraryPicker: () => void;
  selectedDocs: SourceDocument[];
  isDocReady: (doc: SourceDocument) => boolean;
  onRemoveAttachedDoc: (id: string) => void;
  onOpenSourcesDrawer?: () => void;
  onViewPdf?: (filename: string, pageNumber?: number) => void;
  parseMode: 'fast' | 'expert';
  setParseMode: (mode: 'fast' | 'expert') => void;
  isOnline: boolean;
  isListening: boolean;
  isVoiceSpeaking: boolean;
  voiceAudioLevels: number[];
  voiceDurationSec: number;
  formatVoiceDuration: (seconds: number) => string;
  onToggleVoice: () => void;
  onStopVoiceListening: () => void;
  onSubmit: () => void;
}

export const QueryBoxFormActions: React.FC<QueryBoxFormActionsProps> = ({
  query,
  isLoading,
  conversationLength,
  addSourceMenuOpen,
  setAddSourceMenuOpen,
  fileInputRef,
  onFileUpload,
  onOpenLibraryPicker,
  selectedDocs,
  isDocReady,
  onRemoveAttachedDoc,
  onOpenSourcesDrawer,
  onViewPdf,
  parseMode,
  setParseMode,
  isOnline,
  isListening,
  isVoiceSpeaking,
  voiceAudioLevels,
  voiceDurationSec,
  formatVoiceDuration,
  onToggleVoice,
  onStopVoiceListening,
  onSubmit,
}) => {
  return (
    <div
      className={`contents sm:flex sm:order-2 sm:w-full sm:items-center sm:justify-between sm:gap-2 relative z-20 ${
        conversationLength === 0 ? 'sm:pt-1.5' : 'sm:pt-1'
      }`}
    >
      {/* Attachments Section */}
      <div className="order-1 sm:order-none flex items-center gap-1.5 sm:gap-2 shrink-0 select-none">
        <AddSourceButton
          isOpen={addSourceMenuOpen === 'input'}
          onToggle={() => setAddSourceMenuOpen((prev) => (prev === 'input' ? null : 'input'))}
          onClose={() => setAddSourceMenuOpen(null)}
          fileInputRef={fileInputRef}
          onFileUpload={onFileUpload}
          onOpenLibraryPicker={onOpenLibraryPicker}
          parseMode={parseMode}
          onSelectMode={setParseMode}
          conversationLength={conversationLength}
        />
        <AttachedDocChips
          selectedDocs={selectedDocs}
          isDocReady={isDocReady}
          onRemoveDoc={onRemoveAttachedDoc}
          onOpenDrawer={onOpenSourcesDrawer}
          onViewPdf={onViewPdf}
          conversationLength={conversationLength}
          variant="desktop"
        />
      </div>

      {/* Right / Lower Side: Fast/Expert, Mic, and Enter actions */}
      <div className="order-3 sm:order-none flex items-center justify-end space-x-1 sm:space-x-2 shrink-0 ml-auto">
        <FastExpertToggle
          parseMode={parseMode}
          onSelectMode={setParseMode}
          isOnline={isOnline}
          variant="desktop"
        />

        <VoiceInputButton
          isListening={isListening}
          isVoiceSpeaking={isVoiceSpeaking}
          voiceAudioLevels={voiceAudioLevels}
          voiceDurationSec={voiceDurationSec}
          hasSpeechContent={query.trim().length > 0}
          onToggleVoice={onToggleVoice}
          onSubmitVoice={() => {
            onStopVoiceListening();
            onSubmit();
          }}
          formatVoiceDuration={formatVoiceDuration}
        />

        {/* Submit / Stop Button */}
        {(query.trim().length > 0 || isLoading) && (
          <button
            type="submit"
            title={isLoading ? 'Stop generating' : 'Send question'}
            aria-label={isLoading ? 'Stop generating query process' : 'Execute RAG Query'}
            className={`${
              conversationLength === 0
                ? 'w-7.5 h-7.5 sm:w-8 sm:h-8'
                : 'w-6.5 h-6.5 sm:w-8 sm:h-8'
            } rounded-full transition-all flex items-center justify-center shrink-0 bg-slate-900 text-white hover:bg-slate-800 dark:bg-white dark:text-black dark:hover:bg-slate-200 shadow-md cursor-pointer active:scale-95 animate-in fade-in zoom-in-90 duration-150`}
          >
            {isLoading ? (
              <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-xs bg-white dark:bg-black" />
            ) : (
              <svg
                className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white dark:text-black"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  d="M5 10l7-7m0 0l7 7m-7-7v18"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                />
              </svg>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
