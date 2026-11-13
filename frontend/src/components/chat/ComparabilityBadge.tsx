import {
  AlertTriangle,
  CheckCircle2,
  Globe,
  HelpCircle,
  MinusCircle,
  Sliders,
} from 'lucide-react';
import type React from 'react';

export type ComparabilityStatusType =
  | 'FULLY_COMPARABLE'
  | 'CONDITIONALLY_COMPARABLE'
  | 'CONTEXT_ADJUSTED'
  | 'NOT_COMPARABLE'
  | 'INSUFFICIENT_EVIDENCE'
  | 'EXTERNAL_SUPPLEMENTED'
  | 'EXTERNAL_PUBLIC_RECORD';

export const COMPARABILITY_STATUSES: Record<
  ComparabilityStatusType,
  {
    label: string;
    classes: string;
    icon: React.ReactNode;
    tooltip: string;
  }
> = {
  FULLY_COMPARABLE: {
    label: 'Fully Comparable',
    classes:
      'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20',
    icon: <CheckCircle2 className="w-3 h-3 text-emerald-500" />,
    tooltip: 'Directly comparable metrics with standard methodology.',
  },
  CONDITIONALLY_COMPARABLE: {
    label: 'Conditionally Comparable',
    classes:
      'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20',
    icon: <AlertTriangle className="w-3 h-3 text-amber-500" />,
    tooltip: 'Comparable with caveats or differing baseline assumptions.',
  },
  CONTEXT_ADJUSTED: {
    label: 'Context Adjusted',
    classes:
      'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30 hover:bg-sky-500/20',
    icon: <Sliders className="w-3 h-3 text-sky-500" />,
    tooltip: 'Normalized for scale, age, or institutional size differences.',
  },
  NOT_COMPARABLE: {
    label: 'Not Comparable',
    classes:
      'bg-slate-500/10 text-slate-700 dark:text-slate-400 border-slate-500/30 hover:bg-slate-500/20',
    icon: <MinusCircle className="w-3 h-3 text-slate-500" />,
    tooltip: 'Non-overlapping frameworks; direct comparison would mislead.',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence',
    classes:
      'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/30 hover:bg-orange-500/20',
    icon: <HelpCircle className="w-3 h-3 text-orange-500" />,
    tooltip: 'Evidence missing from attached PDF reports.',
  },
  EXTERNAL_SUPPLEMENTED: {
    label: 'External Web Supplemented',
    classes:
      'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/30 hover:bg-purple-500/20',
    icon: <Globe className="w-3 h-3 text-purple-500" />,
    tooltip: 'Data fetched via verified public record curl when PDF was silent.',
  },
  EXTERNAL_PUBLIC_RECORD: {
    label: 'Public Web Record',
    classes:
      'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/30 hover:bg-purple-500/20',
    icon: <Globe className="w-3 h-3 text-purple-500" />,
    tooltip: 'Official institutional registry public record.',
  },
};

export interface ComparabilityBadgeProps {
  status: ComparabilityStatusType | string;
  showIcon?: boolean;
  className?: string;
}

export function normalizeComparabilityKey(text: string): string {
  return text
    .replace(/[`*]/g, '')
    .replace(/^[\p{Emoji}\p{Symbol}\s]+/u, '')
    .trim()
    .toUpperCase();
}

export const ComparabilityBadge: React.FC<ComparabilityBadgeProps> = ({
  status,
  showIcon = true,
  className = '',
}) => {
  const normalizedKey = normalizeComparabilityKey(status) as ComparabilityStatusType;

  const config = COMPARABILITY_STATUSES[normalizedKey];

  if (!config) {
    return <span className={`font-mono text-xs ${className}`}>{status}</span>;
  }

  return (
    <span
      title={config.tooltip}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-tight border transition-colors select-none ${config.classes} ${className}`}
    >
      {showIcon && config.icon}
      <span>{config.label}</span>
    </span>
  );
};

export function isComparabilityStatus(text: string): boolean {
  const clean = normalizeComparabilityKey(text);
  return clean in COMPARABILITY_STATUSES;
}
