import type React from 'react';
import { useState } from 'react';
import { settingsJunction } from '../settings/junction';
import { useBackendConnection } from '../../hooks/useBackendConnection';

export interface UnconfiguredNoticeProps {
  isTunnelConfigured: boolean;
  onOpenSettings?: () => void;
}

export const UnconfiguredNotice: React.FC<UnconfiguredNoticeProps> = ({
  isTunnelConfigured,
  onOpenSettings,
}) => {
  const { connect, scanLocalPorts, isConnecting } = useBackendConnection();
  const [localNotice, setLocalNotice] = useState<string | null>(null);

  if (isTunnelConfigured) return null;

  const handleClick = () => {
    if (onOpenSettings) {
      onOpenSettings();
    } else {
      settingsJunction.open('gateway');
    }
  };

  const handleQuickLocalConnect = async () => {
    setLocalNotice('Probing 127.0.0.1:8000...');
    const res = await connect('http://127.0.0.1:8000');
    if (!res.success) {
      const found = await scanLocalPorts();
      if (!found) {
        setLocalNotice('No local backend on :8000. Start backend with ./START_RAISE.sh');
        setTimeout(() => setLocalNotice(null), 4000);
      }
    }
  };

  return (
    <div className="fixed top-14 sm:top-16 left-0 sm:left-16 right-0 z-30 flex justify-center px-[clamp(0.5rem,2vw,1rem)] pt-1 pointer-events-none animate-in fade-in slide-in-from-top-1 duration-200">
      <div
        data-testid="gateway-unconfigured-notice"
        className="pointer-events-auto inline-flex items-center gap-1.5 sm:gap-2 py-1 px-[clamp(0.625rem,2vw,1rem)] rounded-full bg-amber-500/15 dark:bg-amber-950/75 border border-amber-500/30 text-amber-950 dark:text-amber-200 shadow-sm backdrop-blur-md text-[clamp(10px,2.4vw,12px)] max-w-[calc(100vw-1.5rem)] sm:max-w-none text-center sm:text-left"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
        <p className="leading-tight truncate sm:whitespace-normal">
          {localNotice ? (
            <span>{localNotice}</span>
          ) : (
            <>
              Backend not connected on 127.0.0.1:8000.{' '}
              <button
                type="button"
                onClick={handleQuickLocalConnect}
                disabled={isConnecting}
                className="font-semibold underline text-amber-800 dark:text-amber-300 hover:text-amber-950 dark:hover:text-white cursor-pointer ml-0.5"
              >
                {isConnecting ? 'Connecting...' : 'Connect Local (:8000)'}
              </button>
              {', or open '}
              <button
                type="button"
                aria-label="Open Settings"
                onClick={handleClick}
                className="font-semibold underline hover:text-amber-950 dark:hover:text-white cursor-pointer"
              >
                Settings
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
};
