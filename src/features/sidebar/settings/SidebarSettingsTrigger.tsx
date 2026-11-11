import type React from 'react';

export interface SidebarSettingsTriggerProps {
  gatewayUsername: string;
  isOnline: boolean;
  isTunnelConfigured?: boolean;
  isDrawerOpen: boolean;
  isUserMenuOpen: boolean;
  onToggleUserMenu: () => void;
  onOpenSettings?: () => void;
}

export const SidebarSettingsTrigger: React.FC<SidebarSettingsTriggerProps> = ({
  gatewayUsername,
  isOnline,
  isTunnelConfigured: _isTunnelConfigured = false,
  isDrawerOpen,
  isUserMenuOpen,
  onToggleUserMenu,
  onOpenSettings: _onOpenSettings,
}) => {
  const displayName = gatewayUsername && gatewayUsername.trim() !== '' ? gatewayUsername : 'Member';
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <button
      id="userGatewayMenuBtn"
      data-testid="user-gateway-menu-btn"
      type="button"
      aria-label={`User status: ${displayName}, ${isOnline ? 'Online' : 'Connected'}`}
      aria-haspopup="menu"
      aria-expanded={isUserMenuOpen}
      onClick={onToggleUserMenu}
      className="w-full flex items-center group cursor-pointer text-left transition-all active:scale-[0.98] py-1 px-1 sm:px-2 rounded-xl hover:bg-slate-100 dark:hover:bg-white/5 relative"
    >
      <div className="w-10 h-10 sm:w-12 sm:h-12 flex items-center justify-center shrink-0 relative">
        <div className="relative flex items-center justify-center w-8 h-8 rounded-full bg-indigo-600 text-white font-bold text-xs shadow-xs shrink-0">
          {initial}
          <span
            data-testid="user-online-dot"
            className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-[#12141d] flex items-center justify-center text-white"
          >
            <svg
              className="w-2 h-2 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
        </div>
      </div>
      <div
        className={`flex-1 flex items-center justify-between pl-1.5 pr-2 min-w-0 overflow-hidden transition-opacity duration-200 ${
          isDrawerOpen ? 'opacity-100' : 'opacity-0 pointer-events-none w-0'
        }`}
      >
        <div className="min-w-0 flex-1 pr-1">
          <div
            className="text-xs sm:text-sm font-medium text-slate-800 dark:text-slate-200 group-hover:text-slate-950 dark:group-hover:text-white truncate"
            data-testid="sidebar-user-name"
          >
            {displayName}
          </div>
          <div className="text-[10px] flex items-center gap-1">
            <span className="text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-0.5">
              <svg
                className="w-2.5 h-2.5 text-emerald-500"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Online
            </span>
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${isUserMenuOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
        </svg>
      </div>
    </button>
  );
};
