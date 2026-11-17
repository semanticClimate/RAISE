import { AlertTriangle, CheckCircle2, ChevronDown, ShieldCheck } from 'lucide-react';
import type React from 'react';
import { useState } from 'react';

export interface VerifiedClaimItem {
  claim_id?: string;
  claim_text?: string;
  text?: string;
  verdict?: 'ENTAILMENT' | 'SUPPORTED' | 'NEUTRAL' | 'CONTRADICTION' | 'UNSUPPORTED' | string;
  status?: string;
  is_supported?: boolean;
  confidence?: number;
  source_citation_indices?: number[];
  citations_found?: number[];
  notes?: string[];
}

export interface VerifiedClaimsBadgeProps {
  claims?: VerifiedClaimItem[];
  className?: string;
}

/**
 * Expandable Verified Claims & NLI Badge:
 * Renders below the AI response answer to communicate factual grounding.
 * - ENTAILMENT / SUPPORTED -> Green checkmark badge ("Claim Verified")
 * - NEUTRAL / CONTRADICTION -> Yellow advisory badge ("Review Cited Sources")
 */
export const VerifiedClaimsBadge: React.FC<VerifiedClaimsBadgeProps> = ({
  claims = [],
  className = '',
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!claims || claims.length === 0) return null;

  const normalized = claims.map((c, idx) => {
    const text = c.claim_text || c.text || '';
    const rawVerdict = String(
      c.verdict || c.status || (c.is_supported ? 'ENTAILMENT' : 'UNSUPPORTED')
    ).toUpperCase().trim();

    const isEntailed =
      rawVerdict === 'ENTAILMENT' ||
      rawVerdict === 'SUPPORTED' ||
      rawVerdict === 'DIRECT' ||
      rawVerdict === 'NLI_ENTAILED' ||
      c.is_supported === true;

    const confidence =
      typeof c.confidence === 'number'
        ? Math.round(c.confidence <= 1 ? c.confidence * 100 : c.confidence)
        : null;

    const sources = c.source_citation_indices || c.citations_found || [];

    return {
      id: c.claim_id || `claim-${idx}`,
      text,
      verdict: rawVerdict,
      isEntailed,
      confidence,
      sources,
    };
  });

  const allEntailed = normalized.every((c) => c.isEntailed);
  const unverifiedCount = normalized.filter((c) => !c.isEntailed).length;

  return (
    <div className={`verified-claims-container mt-3 select-none ${className}`}>
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium border transition-all cursor-pointer shadow-2xs ${
          allEntailed
            ? 'bg-emerald-50/80 dark:bg-emerald-500/10 border-emerald-200/80 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100/70 dark:hover:bg-emerald-500/15'
            : 'bg-amber-50/80 dark:bg-amber-500/10 border-amber-300/80 dark:border-amber-500/25 text-amber-700 dark:text-amber-300 hover:bg-amber-100/70 dark:hover:bg-amber-500/15'
        }`}
        aria-expanded={isExpanded}
      >
        {allEntailed ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
        )}
        <span className="font-medium tracking-tight">
          {allEntailed
            ? normalized.length === 1
              ? 'Claim Verified'
              : `All Claims Verified (${normalized.length})`
            : `Review Cited Sources (${unverifiedCount} unverified)`}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-slate-400 dark:text-slate-500 transition-transform ${
            isExpanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 text-xs bg-slate-50 dark:bg-[#111420] border border-slate-200 dark:border-white/10 rounded-xl space-y-2.5 animate-in fade-in max-w-xl shadow-sm">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 dark:text-slate-400 tracking-wide uppercase">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-500" />
            <span>NLI Natural Language Inference Claims:</span>
          </div>

          <div className="space-y-2">
            {normalized.map((claim, idx) => (
              <div
                key={claim.id || idx}
                className="p-2 rounded-lg bg-white dark:bg-white/[0.03] border border-slate-200/60 dark:border-white/5 space-y-1.5 select-text"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded-full inline-flex items-center gap-1 ${
                        claim.isEntailed
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                          : claim.verdict === 'CONTRADICTION'
                            ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                            : 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                      }`}
                    >
                      {claim.isEntailed ? (
                        <CheckCircle2 className="w-2.5 h-2.5 shrink-0" />
                      ) : (
                        <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
                      )}
                      <span>
                        {claim.isEntailed
                          ? 'Entailed'
                          : claim.verdict === 'CONTRADICTION'
                            ? 'Contradiction'
                            : 'Neutral / Review'}
                      </span>
                    </span>

                    {claim.confidence !== null && (
                      <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">
                        {claim.confidence}% confidence
                      </span>
                    )}
                  </div>

                  {claim.sources.length > 0 && (
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                        Sources:
                      </span>
                      {claim.sources.map((srcIdx) => (
                        <span
                          key={srcIdx}
                          className="font-mono text-[10px] font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1 rounded"
                        >
                          [{srcIdx}]
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {claim.text && (
                  <p className="text-[12px] text-slate-700 dark:text-slate-300 leading-relaxed font-normal">
                    {claim.text}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
