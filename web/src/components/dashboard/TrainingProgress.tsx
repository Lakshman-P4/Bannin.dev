'use client';

import { useState } from 'react';
import { Activity, CheckCircle, AlertTriangle, ChevronDown } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { formatDuration, formatRelativeTime, cn } from '@/lib/utils';
import type { TrainingStatus, TrainingTask, DetectedTask } from '@/types';

interface TrainingProgressProps {
  training: TrainingStatus | null;
  onStopTask?: (taskId: string) => void;
}

const STATUS_BADGE: Record<TrainingTask['status'], 'info' | 'success' | 'warning'> = {
  running: 'info',
  completed: 'success',
  stalled: 'warning',
};

function TaskRow({
  task,
  expandedId,
  onToggle,
  onStopTask,
}: {
  task: TrainingTask;
  expandedId: string | null;
  onToggle: (id: string) => void;
  onStopTask?: (taskId: string) => void;
}) {
  const percent = Math.round(task.percentComplete);
  const isExpanded = expandedId === task.id;

  return (
    <li>
      <button
        type="button"
        onClick={() => onToggle(task.id)}
        className="w-full text-left space-y-2"
        aria-expanded={isExpanded}
        aria-controls={`task-detail-${task.id}`}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-primary truncate max-w-[60%]">
            {task.name}
          </span>
          <div className="flex items-center gap-2">
            {task.source !== 'unknown' && (
              <span className="text-[10px] text-text-muted font-mono">{task.source}</span>
            )}
            <Badge variant={STATUS_BADGE[task.status]}>{task.status}</Badge>
          </div>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-surface-raised"
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${task.name}: ${percent}% complete`}
        >
          <div
            className={cn(
              'h-full rounded-full transition-all duration-700',
              task.status === 'stalled' ? 'bg-status-amber' : 'bg-accent-cyan',
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-text-muted font-mono">
          <span>
            {task.current}{task.total != null ? `/${task.total}` : ''} ({percent}%)
          </span>
          <span>
            {task.etaSeconds != null
              ? `ETA: ${task.etaHuman ?? formatDuration(task.etaSeconds)}`
              : `Elapsed: ${formatDuration(task.elapsedSeconds)}`}
          </span>
        </div>
      </button>

      {isExpanded && (
        <div
          id={`task-detail-${task.id}`}
          className="mt-2 p-3 rounded-lg bg-surface-raised/40 text-xs space-y-1.5 animate-fade-in"
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono">
            <span className="text-text-muted">Source</span>
            <span className="text-text-secondary">{task.source}</span>
            <span className="text-text-muted">Progress</span>
            <span className="text-text-secondary">
              {task.current}/{task.total ?? 'unknown'}
            </span>
            {task.startedAt && (
              <>
                <span className="text-text-muted">Started</span>
                <span className="text-text-secondary">
                  {formatRelativeTime(task.startedAt)}
                </span>
              </>
            )}
            <span className="text-text-muted">Elapsed</span>
            <span className="text-text-secondary">{formatDuration(task.elapsedSeconds)}</span>
            {task.etaSeconds != null && (
              <>
                <span className="text-text-muted">ETA</span>
                <span className="text-text-secondary">
                  {task.etaHuman ?? formatDuration(task.etaSeconds)}
                </span>
              </>
            )}
          </div>

          {task.status === 'running' && onStopTask && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onStopTask(task.id);
              }}
              className={cn(
                'mt-2 w-full rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                'border-status-red/20 bg-status-red/10 text-status-red',
                'hover:bg-status-red/20 focus-visible:ring-2 focus-visible:ring-status-red/40',
              )}
              aria-label={`Stop training: ${task.name}`}
            >
              Stop training
            </button>
          )}
        </div>
      )}
    </li>
  );
}

function CompletedRow({ task }: { task: TrainingTask }) {
  return (
    <li className="flex items-center gap-2.5 py-1.5">
      <CheckCircle size={14} className="shrink-0 text-status-green" aria-hidden="true" />
      <span className="text-sm text-text-primary truncate flex-1">{task.name}</span>
      <span className="text-xs text-text-muted font-mono shrink-0">
        {formatDuration(task.elapsedSeconds)}
      </span>
    </li>
  );
}

function DetectedRow({
  task,
  onStopTask,
}: {
  task: DetectedTask;
  onStopTask?: (taskId: string) => void;
}) {
  return (
    <li className="flex items-center gap-2 text-xs">
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full shrink-0',
          task.status === 'running' ? 'bg-status-green' : 'bg-text-muted',
        )}
        aria-hidden="true"
      />
      <span className="text-text-primary truncate flex-1">{task.name}</span>
      <span className="text-text-muted font-mono shrink-0">
        CPU {Math.round(task.cpuPercent)}%
      </span>
      <span className="text-text-muted font-mono shrink-0">
        RAM {Math.round(task.memoryPercent)}%
      </span>
      <span className="text-text-muted font-mono shrink-0">{task.elapsedHuman}</span>
      {task.status === 'running' && onStopTask && (
        <button
          type="button"
          onClick={() => onStopTask(`pid_${task.pid}`)}
          className={cn(
            'shrink-0 rounded border px-2 py-0.5 font-medium transition-colors',
            'border-status-red/20 bg-status-red/10 text-status-red',
            'hover:bg-status-red/20 focus-visible:ring-2 focus-visible:ring-status-red/40',
          )}
          aria-label={`Stop training: ${task.name}`}
        >
          Stop
        </button>
      )}
    </li>
  );
}

export function TrainingProgress({ training, onStopTask }: TrainingProgressProps) {
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [completedExpanded, setCompletedExpanded] = useState(false);

  const activeTasks = training?.activeTasks ?? [];
  const stalledTasks = training?.stalledTasks ?? [];
  const completedTasks = training?.completedTasks ?? [];
  const detectedTasks = training?.detectedTasks ?? [];

  const hasAnyTask =
    activeTasks.length > 0 ||
    stalledTasks.length > 0 ||
    completedTasks.length > 0 ||
    detectedTasks.length > 0;

  const urgency = stalledTasks.length > 0 ? 'warning' as const : 'normal' as const;

  const toggleExpand = (id: string) => {
    setExpandedTaskId((prev) => (prev === id ? null : id));
  };

  if (!hasAnyTask) {
    return (
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-text-muted" aria-hidden="true" />
          <h3 className="text-sm font-medium text-text-secondary">Training Progress</h3>
        </div>
        <p className="text-sm text-text-muted">
          No training runs detected. Bannin watches for tqdm progress bars,
          epoch/step patterns in stdout, and training scripts in running processes.
        </p>
      </Card>
    );
  }

  return (
    <Card urgency={urgency}>
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-accent-cyan" aria-hidden="true" />
        <h3 className="text-sm font-medium text-text-secondary">Training Progress</h3>
      </div>

      {/* Active tasks */}
      {activeTasks.length > 0 && (
        <ul className="space-y-3" aria-label="Active training tasks">
          {activeTasks.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              expandedId={expandedTaskId}
              onToggle={toggleExpand}
              onStopTask={onStopTask}
            />
          ))}
        </ul>
      )}

      {/* Stalled tasks */}
      {stalledTasks.length > 0 && (
        <div className={activeTasks.length > 0 ? 'mt-4' : ''}>
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle size={13} className="text-status-amber" aria-hidden="true" />
            <h4 className="text-xs font-medium text-status-amber">
              Stalled ({stalledTasks.length})
            </h4>
          </div>
          <ul className="space-y-3" aria-label="Stalled training tasks">
            {stalledTasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                expandedId={expandedTaskId}
                onToggle={toggleExpand}
              />
            ))}
          </ul>
        </div>
      )}

      {/* Completed tasks (collapsible) */}
      {completedTasks.length > 0 && (
        <div className="border-t border-surface-border mt-4 pt-3">
          <button
            type="button"
            onClick={() => setCompletedExpanded((prev) => !prev)}
            className="flex items-center gap-1.5 w-full text-left"
            aria-expanded={completedExpanded}
          >
            <ChevronDown
              size={14}
              className={cn(
                'transition-transform text-text-muted',
                completedExpanded && 'rotate-180',
              )}
              aria-hidden="true"
            />
            <CheckCircle size={13} className="text-status-green" aria-hidden="true" />
            <span className="text-xs font-medium text-text-secondary">
              Completed ({completedTasks.length})
            </span>
          </button>
          {completedExpanded && (
            <ul className="mt-2 space-y-0.5" aria-label="Completed training tasks">
              {completedTasks.slice(0, 5).map((task) => (
                <CompletedRow key={task.id} task={task} />
              ))}
              {completedTasks.length > 5 && (
                <li className="text-[10px] text-text-muted pt-1">
                  +{completedTasks.length - 5} more
                </li>
              )}
            </ul>
          )}
        </div>
      )}

      {/* Detected training processes */}
      {detectedTasks.length > 0 && (
        <div className="border-t border-surface-border mt-4 pt-3">
          <h4 className="text-xs font-medium text-text-secondary mb-2">
            Detected Training Processes
          </h4>
          <ul className="space-y-1.5" aria-label="Detected training processes">
            {detectedTasks.slice(0, 5).map((task) => (
              <DetectedRow key={task.pid} task={task} onStopTask={onStopTask} />
            ))}
            {detectedTasks.length > 5 && (
              <li className="text-[10px] text-text-muted pt-1">
                +{detectedTasks.length - 5} more
              </li>
            )}
          </ul>
        </div>
      )}
    </Card>
  );
}
