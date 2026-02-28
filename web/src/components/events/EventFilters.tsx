'use client';

import { cn } from '@/lib/utils';

interface EventFiltersProps {
  type: string;
  severity: string;
  since: string;
  onTypeChange: (type: string) => void;
  onSeverityChange: (severity: string) => void;
  onSinceChange: (since: string) => void;
}

const TYPES = [
  { value: '', label: 'All' },
  { value: 'alert', label: 'Alerts' },
  { value: 'training', label: 'Training' },
  { value: 'oom', label: 'OOM' },
  { value: 'system', label: 'System' },
] as const;

const SEVERITIES = [
  { value: '', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'info', label: 'Info' },
] as const;

const TIME_RANGES = [
  { value: '1h', label: 'Last hour' },
  { value: '24h', label: 'Last 24h' },
  { value: '7d', label: 'Last 7 days' },
] as const;

function ChipGroup({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  return (
    <fieldset>
      <legend className="sr-only">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              value === opt.value
                ? 'border-accent-cyan/30 bg-accent-cyan/10 text-accent-cyan'
                : 'border-surface-border bg-surface-card text-text-secondary hover:text-text-primary',
            )}
            aria-pressed={value === opt.value}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function EventFilters({
  type,
  severity,
  since,
  onTypeChange,
  onSeverityChange,
  onSinceChange,
}: EventFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <ChipGroup options={TYPES} value={type} onChange={onTypeChange} label="Event type" />
      <ChipGroup options={SEVERITIES} value={severity} onChange={onSeverityChange} label="Severity" />
      <ChipGroup options={TIME_RANGES} value={since} onChange={onSinceChange} label="Time range" />
    </div>
  );
}
