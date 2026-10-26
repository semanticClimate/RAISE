import React from 'react';

export interface ActionTooltipProps {
  label: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom';
  className?: string;
}

/**
 * ActionTooltip Component
 * Uses standard/default browser tooltips (title attribute) without floating translucent/blurry card popups.
 */
export const ActionTooltip: React.FC<ActionTooltipProps> = ({
  label,
  children,
  className = '',
}) => {
  if (React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<any>, {
      title: (children.props as any).title || label,
      className: className
        ? `${(children.props as any).className || ''} ${className}`.trim()
        : (children.props as any).className,
    });
  }
  return (
    <span title={label} className={className}>
      {children}
    </span>
  );
};
