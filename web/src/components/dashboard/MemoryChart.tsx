'use client';

import { useId, useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import { Card } from '@/components/ui/Card';
import type { MetricSnapshot } from '@/types';

interface MemoryChartProps {
  history: MetricSnapshot[];
}

export function MemoryChart({ history }: MemoryChartProps) {
  const gradientId = useId();
  const data = useMemo(
    () =>
      history.map((s) => ({
        time: new Date(s.timestamp).toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
        }),
        memory: Math.round(s.memory * 10) / 10,
      })),
    [history],
  );

  return (
    <Card>
      <h3 className="text-sm font-medium text-text-secondary mb-3">Memory Trend</h3>
      {data.length < 2 ? (
        <p className="text-sm text-text-muted">Collecting data...</p>
      ) : (
        <div className="h-48" role="img" aria-label="Memory usage over time">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                tick={{ fill: '#5a7090', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: '#5a7090', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0a0c10',
                  border: '1px solid #141c28',
                  borderRadius: 8,
                  fontSize: 12,
                  color: '#e4ecf7',
                }}
                labelStyle={{ color: '#5a7090' }}
              />
              <Area
                type="monotone"
                dataKey="memory"
                stroke="#00d4ff"
                strokeWidth={2}
                fill={`url(#${gradientId})`}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
