import { AlertTriangle, RotateCw } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

export interface SectionErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  className?: string;
  onReset?: () => void;
}

interface SectionErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Localized Error Boundary that isolates rendering exceptions to specific components
 * (such as Document Viewer, Citation Badges, or Preview Cards) without crashing
 * the chat stream, query box, or workstation shell.
 */
export class SectionErrorBoundary extends Component<
  SectionErrorBoundaryProps,
  SectionErrorBoundaryState
> {
  public state: SectionErrorBoundaryState = { hasError: false, error: null };

  public static getDerivedStateFromError(error: Error): SectionErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn('[SectionErrorBoundary Caught]', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          className={`p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-slate-200 text-xs flex items-center justify-between gap-3 ${
            this.props.className || ''
          }`}
          role="alert"
        >
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="truncate">
              {this.props.fallbackTitle || 'Component could not be rendered'}
            </span>
          </div>
          <button
            type="button"
            onClick={this.handleReset}
            className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-[11px] font-medium flex items-center gap-1 cursor-pointer shrink-0 transition-colors"
          >
            <RotateCw className="w-3 h-3" /> Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
