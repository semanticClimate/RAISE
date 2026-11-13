import type React from 'react';
import { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/contrib/mhchem.mjs';

export interface KaTexRendererProps {
  formula: string;
  displayMode?: boolean;
  className?: string;
}

/**
 * KaTexRenderer Component
 * Fast, synchronous, modular LaTeX mathematical and chemical formula renderer powered by KaTeX + mhchem.
 * Handles:
 * - Inline math: $...$
 * - Block equations: $$...$$
 * - Chemistry formulas via mhchem: $\ce{H2O}$, $\ce{Cu^{2+}}$, $\ce{-S-S-}$, $\ce{Fe3O4}$
 */
export const KaTexRenderer: React.FC<KaTexRendererProps> = ({
  formula,
  displayMode = false,
  className = '',
}) => {
  const renderedHtml = useMemo(() => {
    try {
      return katex.renderToString(formula, {
        displayMode,
        throwOnError: false,
        errorColor: '#ef4444',
        output: 'htmlAndMathml',
        strict: false,
        trust: false,
      });
    } catch {
      return null;
    }
  }, [formula, displayMode]);

  if (!renderedHtml) {
    return (
      <code
        className={`font-mono text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.08] text-amber-800 dark:text-amber-200 ${className}`}
        title="LaTeX Formula"
      >
        {formula}
      </code>
    );
  }

  if (displayMode) {
    return (
      <div
        className={`my-3.5 py-3.5 px-4 rounded-xl bg-slate-50/90 dark:bg-[#111420]/90 border border-slate-200/80 dark:border-white/10 overflow-x-auto shadow-2xs text-center text-slate-900 dark:text-slate-100 scrollbar-thin ${className}`}
        data-testid="katex-block-equation"
      >
        <div className="inline-block py-1 px-2 select-text font-serif">
          <span dangerouslySetInnerHTML={{ __html: renderedHtml }} />
        </div>
      </div>
    );
  }

  return (
    <span
      className={`inline-block mx-0.5 align-baseline select-text text-slate-900 dark:text-slate-100 font-serif ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
      data-testid="katex-inline-formula"
    />
  );
};

export const MathBlock: React.FC<Omit<KaTexRendererProps, 'displayMode'>> = (props) => (
  <KaTexRenderer {...props} displayMode={true} />
);

export default KaTexRenderer;
