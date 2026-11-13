import React from 'react';
import { KaTexRenderer } from '../KaTexRenderer';
import { CodeBlock } from './CodeBlock';
import { TableBlock } from './TableBlock';
import type { Block } from './markdownTypes';
import { type RenderInlineOptions, renderInlineContent } from './renderInline';

export interface MemoizedMarkdownBlockProps {
  block: Block;
  blockIdx: number;
  inlineOptions: RenderInlineOptions;
}

export const MemoizedMarkdownBlockBase: React.FC<MemoizedMarkdownBlockProps> = ({
  block,
  blockIdx,
  inlineOptions,
}) => {
  const renderInline = (text: string, keyPrefix: string) =>
    renderInlineContent(text, keyPrefix, inlineOptions);

  switch (block.type) {
    case 'heading': {
      if (block.level === 1) {
        return (
          <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-slate-900 dark:text-white mt-6 mb-2.5 pb-2 border-b border-slate-200/80 dark:border-white/10">
            {renderInline(block.text, `h1-${blockIdx}`)}
          </h2>
        );
      }
      if (block.level === 2) {
        return (
          <h3 className="text-lg sm:text-xl font-semibold tracking-tight text-slate-900 dark:text-white mt-5 mb-2">
            {renderInline(block.text, `h2-${blockIdx}`)}
          </h3>
        );
      }
      if (block.level === 3) {
        return (
          <h4 className="text-[16.5px] font-semibold text-slate-900 dark:text-white mt-4.5 mb-1.5">
            {renderInline(block.text, `h3-${blockIdx}`)}
          </h4>
        );
      }
      return (
        <h5 className="text-[15px] font-semibold text-slate-900 dark:text-slate-200 mt-3.5 mb-1">
          {renderInline(block.text, `h4-${blockIdx}`)}
        </h5>
      );
    }

    case 'ordered-list': {
      return (
        <ol className="my-3 pl-6 list-decimal space-y-1.5 text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 marker:text-slate-500 dark:marker:text-slate-400 marker:font-medium">
          {block.items.map((item, itemIdx) => (
            <li
              key={itemIdx}
              className={`pl-1 leading-[1.75] ${item.indent > 0 ? 'ml-4' : ''}`}
            >
              {renderInline(item.text, `ol-${blockIdx}-${itemIdx}`)}
            </li>
          ))}
        </ol>
      );
    }

    case 'unordered-list': {
      return (
        <ul className="my-3 pl-6 list-disc space-y-1.5 text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 marker:text-slate-400 dark:marker:text-slate-500">
          {block.items.map((item, itemIdx) => {
            const boldKeyMatch = item.text.match(/^(\*\*[^*]+\*\*:?)\s*([\s\S]*)$/);

            if (boldKeyMatch) {
              const cleanKey = boldKeyMatch[1]
                .replace(/^\*\*|\*\*$/g, '')
                .replace(/:$/, '')
                .trim();
              const value = boldKeyMatch[2].trim();
              return (
                <li
                  key={itemIdx}
                  className={`pl-1 leading-[1.75] ${item.indent > 0 ? 'ml-4 list-[circle]' : ''}`}
                >
                  <strong className="font-semibold text-slate-900 dark:text-white mr-1.5">
                    {cleanKey}:
                  </strong>
                  {value && (
                    <span className="text-slate-800 dark:text-slate-200">
                      {renderInline(value, `ul-v-${blockIdx}-${itemIdx}`)}
                    </span>
                  )}
                </li>
              );
            }

            return (
              <li
                key={itemIdx}
                className={`pl-1 leading-[1.75] ${item.indent > 0 ? 'ml-4 list-[circle]' : ''}`}
              >
                {renderInline(item.text, `ul-${blockIdx}-${itemIdx}`)}
              </li>
            );
          })}
        </ul>
      );
    }

    case 'blockquote': {
      return (
        <blockquote className="border-l-2 border-slate-300 dark:border-slate-700 pl-3.5 py-1.5 my-3 bg-slate-50/70 dark:bg-white/[0.02] rounded-r-lg text-slate-600 dark:text-slate-300 italic text-[14px] leading-relaxed">
          {renderInline(block.text, `bq-${blockIdx}`)}
        </blockquote>
      );
    }

    case 'callout': {
      if (block.variant === 'warning') {
        return (
          <div className="my-3 p-3.5 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/60 text-slate-800 dark:text-slate-200 text-[14px] leading-relaxed flex items-start gap-2.5">
            <span className="text-amber-600 dark:text-amber-400 font-bold shrink-0 mt-0.5">
              ⚠
            </span>
            <div className="flex-1 min-w-0">
              {renderInline(block.text, `callout-warn-${blockIdx}`)}
            </div>
          </div>
        );
      }
      return (
        <div className="my-3 p-3.5 rounded-xl bg-slate-100/70 dark:bg-white/[0.04] border border-slate-200/80 dark:border-white/10 text-slate-800 dark:text-slate-200 text-[14px] leading-relaxed flex items-start gap-2.5">
          <span className="text-slate-500 dark:text-slate-400 font-bold shrink-0 mt-0.5">
            ℹ
          </span>
          <div className="flex-1 min-w-0">
            {renderInline(block.text, `callout-info-${blockIdx}`)}
          </div>
        </div>
      );
    }

    case 'math': {
      return <KaTexRenderer formula={block.formula} displayMode={true} />;
    }

    case 'code': {
      return <CodeBlock code={block.code} language={block.language} />;
    }

    case 'table': {
      return (
        <TableBlock
          tableIdx={blockIdx}
          headers={block.headers}
          alignments={block.alignments}
          rows={block.rows}
          renderInline={renderInline}
        />
      );
    }

    case 'hr': {
      return <hr className="my-5 border-t border-slate-200/80 dark:border-white/10" />;
    }

    default: {
      return (
        <p className="text-[15px] leading-[1.75] text-slate-800 dark:text-slate-200 my-2.5 whitespace-pre-line">
          {renderInline(block.text, `p-${blockIdx}`)}
        </p>
      );
    }
  }
};

function areBlocksEqual(
  prev: MemoizedMarkdownBlockProps,
  next: MemoizedMarkdownBlockProps
): boolean {
  if (prev.blockIdx !== next.blockIdx) return false;
  if (prev.inlineOptions.showCitations !== next.inlineOptions.showCitations) return false;
  if (prev.inlineOptions.onViewPdf !== next.inlineOptions.onViewPdf) return false;
  if (prev.inlineOptions.enrichedCitations.length !== next.inlineOptions.enrichedCitations.length)
    return false;
  if (prev.block === next.block) return true;
  if (prev.block.type !== next.block.type) return false;

  // Cheap structural check before stringify
  switch (prev.block.type) {
    case 'heading':
    case 'blockquote':
    case 'paragraph':
      return prev.block.text === (next.block as typeof prev.block).text;
    case 'code':
      return (
        prev.block.code === (next.block as typeof prev.block).code &&
        prev.block.language === (next.block as typeof prev.block).language
      );
    case 'math':
      return prev.block.formula === (next.block as typeof prev.block).formula;
    case 'hr':
      return true;
    default:
      return JSON.stringify(prev.block) === JSON.stringify(next.block);
  }
}

export const MemoizedMarkdownBlock = React.memo(MemoizedMarkdownBlockBase, areBlocksEqual);
