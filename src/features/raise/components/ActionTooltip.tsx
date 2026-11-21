import React from 'react';
import { SpecialTooltip, type SpecialTooltipProps } from '../../../components/ui/SpecialTooltip';

export type ActionTooltipProps = SpecialTooltipProps;

/**
 * ActionTooltip Component
 * Unified standard tooltip primitive delegating to SpecialTooltip to avoid duplicate code.
 */
export const ActionTooltip: React.FC<ActionTooltipProps> = (props) => {
  return <SpecialTooltip {...props} />;
};

