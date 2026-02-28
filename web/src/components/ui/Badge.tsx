import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-surface-raised text-text-secondary border-surface-border',
  success: 'bg-status-green/10 text-status-green border-status-green/20',
  warning: 'bg-status-amber/10 text-status-amber border-status-amber/20',
  danger: 'bg-status-red/10 text-status-red border-status-red/20',
  info: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/20',
};

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
