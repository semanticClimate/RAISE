import React from 'react';
import { RAISE_LAYOUT } from '../../../styles/layoutTokens';

export interface RaiseHeroHeaderProps {
  hasSourcesAttached: boolean;
}

export const RaiseHeroHeader: React.FC<RaiseHeroHeaderProps> = ({ hasSourcesAttached }) => {
  return (
    <section className={RAISE_LAYOUT.queryHeader} data-purpose="hero-header">
      <div>
        <h1 className="text-[clamp(1.5rem,4.5vw,2.25rem)] font-semibold tracking-tight text-slate-900 dark:text-white mb-1.5">
          Welcome to RAISE
        </h1>
        <p className="text-[clamp(0.8125rem,2.2vw,0.9375rem)] text-slate-500 dark:text-slate-400 font-normal leading-relaxed">
          {hasSourcesAttached
            ? 'Explore insights from your attached sources or ask a follow-up inquiry.'
            : 'Ask research questions, synthesize knowledge, or attach documents for deep analysis.'}
        </p>
      </div>
    </section>
  );
};
