import { Check, Copy } from 'lucide-react';
import React, { useState } from 'react';

export interface CodeBlockProps {
  code: string;
  language?: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="my-3.5 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 shadow-2xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-800/80 border-b border-slate-700/60 text-[11px] font-mono text-slate-400">
        <span className="font-medium tracking-wide uppercase">{language || 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? 'Copied code' : 'Copy code'}
          title={copied ? 'Copied!' : 'Copy code'}
          className="flex items-center justify-center p-1.5 rounded-md text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700/60 active:scale-95 transition-all cursor-pointer"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Copy className="w-3.5 h-3.5 text-slate-400 hover:text-white" />
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-[12.5px] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
};
