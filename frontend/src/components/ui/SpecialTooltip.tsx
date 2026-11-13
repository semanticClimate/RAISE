import React from 'react';

export interface SpecialTooltipProps {
  label: React.ReactNode;
  position?: 'right' | 'top' | 'bottom' | 'left';
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
}

/**
 * SpecialTooltip Component
 * Uses standard/default browser tooltips without floating translucent/blurry card popups.
 */
export const SpecialTooltip: React.FC<SpecialTooltipProps> = ({
  label,
  children,
  className = '',
  disabled = false,
}) => {
  const titleText = typeof label === 'string' ? label : undefined;
  if (disabled) {
    return <>{children}</>;
  }

  if (React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<any>, {
      title: (children.props as any).title || titleText,
      className: className
        ? `${(children.props as any).className || ''} ${className}`.trim()
        : (children.props as any).className,
    });
  }

  return (
    <span title={titleText} className={className}>
      {children}
    </span>
  );
};
