import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import type { UrgencyLevel } from '@/types';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  urgency?: UrgencyLevel;
  hoverable?: boolean;
  children: ReactNode;
}

const urgencyStyles: Record<UrgencyLevel, string> = {
  normal: '',
  warning: 'urgency-warning',
  critical: 'urgency-critical',
};

export function Card({ urgency = 'normal', hoverable, className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        hoverable ? 'glass-card-hover' : 'glass-card',
        urgencyStyles[urgency],
        'p-5',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
